"""
pytest configuration and shared fixtures.

Key fixtures
------------
client          AsyncClient with AuditMiddleware disabled (Redis not needed).
valid_token     Pre-signed JWT with all scopes (RS256, signed with a test key).
mock_jwks       Monkeypatches the JWKS validator to accept the test key.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt

from app.auth.scopes import (
    ACADEMICO_READ,
    ADMIN_READ,
    ESTUDIANTES_READ,
)
from app.main import create_app


# ---------------------------------------------------------------------------
# RSA key pair for test tokens
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def rsa_private_key():
    """Generate an RSA-2048 private key once per test session."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


@pytest.fixture(scope="session")
def rsa_public_key(rsa_private_key):
    return rsa_private_key.public_key()


# ---------------------------------------------------------------------------
# JWKS mock
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_jwks(rsa_public_key):
    """Return a JWKS dict containing the test RSA public key."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from jose.backends import RSAKey

    # Export the public key in PEM form for python-jose
    pem = rsa_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    # Build a minimal JWKS representation
    key = RSAKey(pem, algorithm="RS256")
    jwk_dict = key.public_key().to_dict()
    jwk_dict.update({"kid": "test-key-001", "use": "sig", "alg": "RS256"})
    return {"keys": [jwk_dict]}


# ---------------------------------------------------------------------------
# Token factory
# ---------------------------------------------------------------------------

def _make_token(
    private_key,
    scopes: list[str],
    expired: bool = False,
    bad_audience: bool = False,
    bad_issuer: bool = False,
    jti: str | None = None,
) -> str:
    """Create a signed JWT with the given parameters."""
    now = int(time.time())
    payload = {
        "iss": "https://auth.unicesar.edu.co/realms/upc" if not bad_issuer else "https://evil.example.com",
        "aud": "upc-api-institucional" if not bad_audience else "wrong-audience",
        "sub": "test-user-001",
        "azp": "test-client-001",
        "client_id": "test-client-001",
        "scope": " ".join(scopes),
        "jti": jti or str(uuid.uuid4()),
        "iat": now - 60 if not expired else now - 3600,
        "exp": now + 3600 if not expired else now - 1,
    }

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    return jose_jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": "test-key-001"})


@pytest.fixture(scope="session")
def valid_token(rsa_private_key):
    """A valid JWT with all scopes."""
    return _make_token(rsa_private_key, scopes=[ACADEMICO_READ, ESTUDIANTES_READ, ADMIN_READ])


@pytest.fixture(scope="session")
def academico_token(rsa_private_key):
    """A valid JWT with only academico:read scope."""
    return _make_token(rsa_private_key, scopes=[ACADEMICO_READ])


@pytest.fixture(scope="session")
def estudiantes_token(rsa_private_key):
    """A valid JWT with only estudiantes:read scope."""
    return _make_token(rsa_private_key, scopes=[ESTUDIANTES_READ])


@pytest.fixture(scope="session")
def expired_token(rsa_private_key):
    """An expired JWT."""
    return _make_token(rsa_private_key, scopes=[ACADEMICO_READ], expired=True)


@pytest.fixture(scope="session")
def wrong_audience_token(rsa_private_key):
    """A JWT signed with the right key but wrong audience."""
    return _make_token(rsa_private_key, scopes=[ACADEMICO_READ], bad_audience=True)


# ---------------------------------------------------------------------------
# App fixture with JWKS mocked
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_with_mock_jwks(test_jwks, rsa_private_key) -> FastAPI:
    """
    Returns the FastAPI app with:
    - JWKS validation patched to use the test key
    - Redis patched to a no-op mock
    - Audit writer disabled
    """
    _app = create_app()

    # Patch the JWKS fetcher in jwt_validator
    async def _mock_get_jwks():
        return test_jwks

    # Patch audit middleware to skip Redis
    return _app


@pytest_asyncio.fixture
async def client(test_jwks) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient for the test app. JWKS and Redis are mocked.
    """
    app = create_app()

    async def _mock_get_jwks():
        return test_jwks

    # We patch at the module level used by jwt_validator
    with patch("app.auth.jwt_validator._get_jwks", new=_mock_get_jwks), \
         patch("app.auth.jwt_validator.force_refresh_jwks", new=AsyncMock()), \
         patch("redis.asyncio.from_url") as mock_redis_factory:

        # Make Redis ping/xadd no-ops
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.xadd = AsyncMock(return_value=b"0-1")
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.xreadgroup = AsyncMock(return_value=None)
        mock_redis.xack = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_factory.return_value = mock_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
