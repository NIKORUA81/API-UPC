"""
Authentication and scope enforcement tests.

Tests
-----
- Missing Authorization header → 401
- Malformed token (not a valid JWT) → 401
- Expired token → 401
- Wrong audience → 401
- Valid token but missing required scope → 403
- Valid token with correct scope → 200
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_auth_header(client: AsyncClient):
    """Request with no Authorization header should return 401."""
    response = await client.get("/v1/academico/programas")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token(client: AsyncClient):
    """A garbage string as Bearer token should return 401."""
    response = await client.get(
        "/v1/academico/programas",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token(client: AsyncClient, expired_token: str):
    """An expired JWT should return 401."""
    response = await client.get(
        "/v1/academico/programas",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_audience(client: AsyncClient, wrong_audience_token: str):
    """A JWT with the wrong audience should return 401."""
    response = await client.get(
        "/v1/academico/programas",
        headers={"Authorization": f"Bearer {wrong_audience_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_scope_returns_403(client: AsyncClient, academico_token: str):
    """
    A token that has academico:read but NOT estudiantes:read should get 403
    when accessing a estudiantes endpoint.
    """
    response = await client.get(
        "/v1/estudiantes/EST-TEST-001/inscripciones",
        headers={"Authorization": f"Bearer {academico_token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_valid_token_grants_access(client: AsyncClient, academico_token: str):
    """A valid token with the correct scope should return 200."""
    response = await client.get(
        "/v1/academico/programas",
        headers={"Authorization": f"Bearer {academico_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_scope_mismatch_academico_on_estudiantes(
    client: AsyncClient, academico_token: str
):
    """academico:read scope should not grant access to estudiantes endpoints."""
    response = await client.get(
        "/v1/estudiantes/EST-TEST-001/calificaciones/2024-1",
        headers={"Authorization": f"Bearer {academico_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_scope_mismatch_estudiantes_on_academico(
    client: AsyncClient, estudiantes_token: str
):
    """estudiantes:read scope should not grant access to academico endpoints."""
    response = await client.get(
        "/v1/academico/periodos",
        headers={"Authorization": f"Bearer {estudiantes_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_no_auth_required(client: AsyncClient):
    """/health endpoint should be accessible without any token."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body


@pytest.mark.asyncio
async def test_detailed_health_requires_admin_scope(
    client: AsyncClient, academico_token: str
):
    """/health/detailed should require admin:read scope."""
    response = await client.get(
        "/health/detailed",
        headers={"Authorization": f"Bearer {academico_token}"},
    )
    assert response.status_code == 403
