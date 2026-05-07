"""
AuditMiddleware — Starlette BaseHTTPMiddleware that logs every request to a
Redis Stream ("upc:audit:stream") for asynchronous processing.

Design decisions
----------------
* Body hashing (SHA-256) only for POST / PUT / PATCH to avoid buffering large
  payloads on GET requests.
* JWT is decoded without re-validating the signature here (it was already
  validated by the auth dependency).  We parse it only to extract ``client_id``
  and ``user_sub``.
* If Redis is unavailable the audit record is logged to stderr and the request
  proceeds normally.
* Path parameters are normalised to ``{param}`` placeholders using a simple
  heuristic so that ``/v1/estudiantes/EST-TEST-001/calificaciones/2024-1``
  becomes ``/v1/estudiantes/{estudianteId}/calificaciones/{periodo}``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from jose import jwt as jose_jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

REDIS_STREAM_KEY = "upc:audit:stream"

# Regex patterns used to normalise path parameters
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_STUDENT_ID_RE = re.compile(r"EST-[A-Z0-9-]+")
_PROGRAM_CODE_RE = re.compile(r"[A-Z]{2,6}-[A-Z]{2,6}-\d{2}")
_PERIODO_RE = re.compile(r"\d{4}-[12]")
_NUMERIC_SEGMENT_RE = re.compile(r"(?<=/)\d+(?=/|$)")


def _normalise_path(path: str) -> str:
    """Replace path parameter values with ``{param}`` placeholders."""
    result = _UUID_RE.sub("{id}", path)
    result = _STUDENT_ID_RE.sub("{estudianteId}", result)
    result = _PROGRAM_CODE_RE.sub("{codigoPrograma}", result)
    result = _PERIODO_RE.sub("{periodo}", result)
    result = _NUMERIC_SEGMENT_RE.sub("{id}", result)
    return result


def _extract_ip(request: Request) -> str:
    """Return the best-guess client IP (X-Forwarded-For aware)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "0.0.0.0"


def _extract_jwt_claims(request: Request) -> tuple[str, str | None, list[str], str | None]:
    """
    Parse the Bearer token (no signature verification) and return
    ``(client_id, user_sub, scopes, jti)``.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return "anonymous", None, [], None

    raw = auth_header[7:].strip()
    try:
        payload: dict[str, Any] = jose_jwt.get_unverified_claims(raw)
        client_id: str = (
            payload.get("client_id")
            or payload.get("azp")
            or payload.get("sub")
            or "unknown"
        )
        user_sub: str | None = payload.get("sub")
        scopes_raw: str = payload.get("scope", "")
        scopes: list[str] = scopes_raw.split() if scopes_raw else []
        jti: str | None = payload.get("jti")
        return client_id, user_sub, scopes, jti
    except Exception:  # noqa: BLE001
        return "unknown", None, [], None


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start_ns = time.perf_counter_ns()

        # --- Read and optionally hash the request body ---
        body_hash: str | None = None
        if request.method.upper() in ("POST", "PUT", "PATCH"):
            body_bytes: bytes = await request.body()
            if body_bytes:
                body_hash = hashlib.sha256(body_bytes).hexdigest()

        # --- Call the actual handler ---
        response: Response = await call_next(request)

        elapsed_ms = (time.perf_counter_ns() - start_ns) // 1_000_000

        # --- Extract audit fields ---
        client_id, user_sub, scopes, jti = _extract_jwt_claims(request)
        ip_origin = _extract_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:500]
        normalised_path = _normalise_path(request.url.path)
        query_params: dict[str, Any] | None = (
            dict(request.query_params) if request.query_params else None
        )

        audit_record: dict[str, str] = {
            "id": str(uuid.uuid4()),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "client_id": client_id,
            "user_sub": user_sub or "",
            "method": request.method,
            "endpoint": normalised_path,
            "query_params": json.dumps(query_params) if query_params else "",
            "request_body_hash": body_hash or "",
            "scopes_used": json.dumps(scopes),
            "ip_origin": ip_origin,
            "user_agent": user_agent,
            "http_status": str(response.status_code),
            "response_time_ms": str(elapsed_ms),
            "token_jti": jti or "",
        }

        # --- Push to Redis Stream (non-blocking) ---
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            try:
                await redis_client.xadd(REDIS_STREAM_KEY, audit_record, maxlen=100_000)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "AuditMiddleware: Redis write failed (non-blocking): %s | record=%s",
                    exc,
                    audit_record,
                )
        else:
            logger.warning(
                "AuditMiddleware: Redis unavailable, audit record dropped: %s",
                audit_record,
            )

        return response
