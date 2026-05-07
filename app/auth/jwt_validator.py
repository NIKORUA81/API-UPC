"""
JWKS-based JWT validation.

Responsibilities:
- Fetch and cache the Keycloak JWKS endpoint (refreshed every JWKS_CACHE_TTL_SECONDS).
- Validate JWT: RS256 signature, issuer, audience, expiry.
- Check token JTI against the Redis blacklist.
- Return the decoded payload dict on success.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level JWKS cache
# ---------------------------------------------------------------------------
_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


async def _get_jwks() -> dict[str, Any]:
    """Return cached JWKS, refreshing if older than JWKS_CACHE_TTL_SECONDS."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < settings.JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    logger.info("Fetching JWKS from %s", settings.KEYCLOAK_JWKS_URL)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.KEYCLOAK_JWKS_URL)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now
        logger.info("JWKS cache refreshed, %d key(s) loaded", len(_jwks_cache.get("keys", [])))

    return _jwks_cache


async def force_refresh_jwks() -> None:
    """Force-invalidate the JWKS cache (called on startup)."""
    global _jwks_fetched_at
    _jwks_fetched_at = 0.0
    await _get_jwks()


async def validate_token(raw_token: str, redis_client: Any | None = None) -> dict[str, Any]:
    """
    Validate *raw_token* and return its decoded payload.

    Raises:
        JWTError: on any validation failure (signature, expiry, issuer, audience, blacklist).
    """
    jwks = await _get_jwks()

    # python-jose accepts the full JWKS dict directly.
    try:
        payload: dict[str, Any] = jwt.decode(
            raw_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.API_AUDIENCE,
            issuer=settings.KEYCLOAK_ISSUER,
            options={"verify_exp": True, "verify_iat": True},
        )
    except ExpiredSignatureError as exc:
        raise JWTError("Token has expired") from exc
    except JWTClaimsError as exc:
        raise JWTError(f"Invalid token claims: {exc}") from exc
    except JWTError:
        raise

    # --- JTI blacklist check ---
    jti: str | None = payload.get("jti")
    if jti and redis_client is not None:
        try:
            blacklisted = await redis_client.exists(f"blacklist:jti:{jti}")
            if blacklisted:
                raise JWTError("Token has been revoked (JTI blacklisted)")
        except Exception as exc:  # noqa: BLE001
            # If Redis is unavailable we log a warning but do NOT fail the request.
            logger.warning("Redis JTI check failed (non-blocking): %s", exc)

    return payload
