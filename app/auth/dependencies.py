"""
FastAPI dependencies for authentication and scope enforcement.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt_validator import validate_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Core token dependency
# ---------------------------------------------------------------------------

async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """
    Extract and validate the Bearer token.
    Returns the decoded JWT payload dict.
    Raises HTTP 401 on any validation failure.
    """
    redis_client = getattr(request.app.state, "redis", None)

    try:
        payload = await validate_token(credentials.credentials, redis_client=redis_client)
    except JWTError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "UNAUTHORIZED",
                "message": str(exc),
                "timestamp": _utcnow_iso(),
                "requestId": _new_request_id(),
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return payload


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------

def require_scope(required_scope: str) -> Callable[..., dict[str, Any]]:
    """
    Dependency factory: returns a FastAPI dependency that verifies the JWT
    payload contains *required_scope* in its ``scope`` claim.

    Usage::

        @router.get("/resource")
        async def endpoint(
            token_data: dict = Depends(require_scope(ACADEMICO_READ))
        ): ...
    """

    async def _check_scope(
        token_data: dict[str, Any] = Depends(get_current_token),
    ) -> dict[str, Any]:
        scopes_raw: str = token_data.get("scope", "")
        token_scopes: list[str] = scopes_raw.split() if scopes_raw else []

        if required_scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "FORBIDDEN",
                    "message": (
                        f"Insufficient scope. Required: '{required_scope}'. "
                        f"Granted: {token_scopes}"
                    ),
                    "timestamp": _utcnow_iso(),
                    "requestId": _new_request_id(),
                },
            )

        return token_data

    return _check_scope


# ---------------------------------------------------------------------------
# Helper: extract client_id
# ---------------------------------------------------------------------------

def get_client_id(token_data: dict[str, Any]) -> str:
    """
    Return the ``client_id`` (or ``azp``) claim from the decoded JWT payload.
    Falls back to the ``sub`` claim, then to "unknown".
    """
    return (
        token_data.get("client_id")
        or token_data.get("azp")
        or token_data.get("sub")
        or "unknown"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _new_request_id() -> str:
    return str(uuid.uuid4())
