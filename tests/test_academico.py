"""
Tests for the /v1/academico endpoints.

Coverage
--------
- GET /v1/academico/programas
    * Returns paginated list
    * Filtering by nivel
    * Filtering by modalidad
    * Pagination (page / limit)
    * limit > 100 is rejected
- GET /v1/academico/programas/{codigo}/asignaturas
    * Returns subjects for a known programme
    * Filtering by semestre
    * Returns 404 for unknown programme
- GET /v1/academico/periodos
    * Returns active periods by default
    * soloActivos=false returns all periods
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# /v1/academico/programas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_programas_returns_paginated_response(
    client: AsyncClient, academico_token: str
):
    """Default request returns a properly shaped PaginatedResponse."""
    response = await client.get(
        "/v1/academico/programas",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "total" in body
    assert "page" in body
    assert "limit" in body
    assert isinstance(body["data"], list)
    assert body["page"] == 1
    assert body["limit"] == 20
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_programas_contains_expected_fields(
    client: AsyncClient, academico_token: str
):
    """Each programme item should contain the required fields."""
    response = await client.get(
        "/v1/academico/programas",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    first = data[0]
    required_keys = {
        "codigoPrograma", "nombrePrograma", "facultad", "nivel",
        "modalidad", "creditosTotales", "duracionSemestres", "acreditado",
    }
    assert required_keys.issubset(first.keys())


@pytest.mark.asyncio
async def test_list_programas_filter_by_nivel(
    client: AsyncClient, academico_token: str
):
    """Filtering by nivel=PREGRADO should only return PREGRADO programmes."""
    response = await client.get(
        "/v1/academico/programas?nivel=PREGRADO",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert all(p["nivel"] == "PREGRADO" for p in data)


@pytest.mark.asyncio
async def test_list_programas_filter_by_modalidad(
    client: AsyncClient, academico_token: str
):
    """Filtering by modalidad=PRESENCIAL should only return PRESENCIAL programmes."""
    response = await client.get(
        "/v1/academico/programas?modalidad=PRESENCIAL",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert all(p["modalidad"] == "PRESENCIAL" for p in data)


@pytest.mark.asyncio
async def test_list_programas_pagination(client: AsyncClient, academico_token: str):
    """Requesting page=1&limit=2 should return at most 2 items."""
    response = await client.get(
        "/v1/academico/programas?page=1&limit=2",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) <= 2
    assert body["page"] == 1
    assert body["limit"] == 2


@pytest.mark.asyncio
async def test_list_programas_limit_exceeds_max(
    client: AsyncClient, academico_token: str
):
    """Requesting limit=101 should return 422 (validation error)."""
    response = await client.get(
        "/v1/academico/programas?limit=101",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /v1/academico/programas/{codigoPrograma}/asignaturas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_asignaturas_known_programme(
    client: AsyncClient, academico_token: str
):
    """Requesting subjects for ING-SIS-01 should return a non-empty list."""
    response = await client.get(
        "/v1/academico/programas/ING-SIS-01/asignaturas",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_list_asignaturas_contains_required_fields(
    client: AsyncClient, academico_token: str
):
    """Each subject item should contain the required fields."""
    response = await client.get(
        "/v1/academico/programas/ING-SIS-01/asignaturas",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    first = data[0]
    required_keys = {
        "codigoAsignatura", "nombreAsignatura", "creditos",
        "semestre", "tipoAsignatura", "areaFormacion", "horasSemanales",
    }
    assert required_keys.issubset(first.keys())


@pytest.mark.asyncio
async def test_list_asignaturas_filter_by_semestre(
    client: AsyncClient, academico_token: str
):
    """Filtering by semestre=1 should only return first-semester subjects."""
    response = await client.get(
        "/v1/academico/programas/ING-SIS-01/asignaturas?semestre=1",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert all(s["semestre"] == 1 for s in data)


@pytest.mark.asyncio
async def test_list_asignaturas_unknown_programme_returns_404(
    client: AsyncClient, academico_token: str
):
    """Requesting subjects for a non-existent programme should return 404."""
    response = await client.get(
        "/v1/academico/programas/NOT-EXIST-99/asignaturas",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# /v1/academico/periodos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_periodos_default_only_active(
    client: AsyncClient, academico_token: str
):
    """Default behaviour (soloActivos=true) returns only active periods."""
    response = await client.get(
        "/v1/academico/periodos",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert all(p["activo"] for p in data)


@pytest.mark.asyncio
async def test_list_periodos_all(client: AsyncClient, academico_token: str):
    """soloActivos=false should return all periods including inactive ones."""
    response = await client.get(
        "/v1/academico/periodos?soloActivos=false",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should have more periods when we include inactive ones
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_list_periodos_contains_required_fields(
    client: AsyncClient, academico_token: str
):
    """Each period item should contain the required fields."""
    response = await client.get(
        "/v1/academico/periodos?soloActivos=false",
        headers=auth_header(academico_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    first = data[0]
    required_keys = {
        "codigoPeriodo", "nombrePeriodo", "fechaInicio",
        "fechaFin", "activo", "periodoMatriculas",
    }
    assert required_keys.issubset(first.keys())
