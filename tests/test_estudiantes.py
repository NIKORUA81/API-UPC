"""
Tests for the /v1/estudiantes endpoints.

Coverage
--------
- GET /v1/estudiantes/{estudianteId}/inscripciones
    * Returns enrollment list for EST-TEST-001
    * Filtering by periodo
    * Returns 404 for unknown student
- GET /v1/estudiantes/{estudianteId}/calificaciones/{periodo}
    * Returns grades for EST-TEST-001 in a valid period
    * Returns 404 for unknown student
    * Returns 404 for unknown period
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

TEST_STUDENT = "EST-TEST-001"
VALID_PERIODO = "2024-1"
INVALID_STUDENT = "EST-DOES-NOT-EXIST"
INVALID_PERIODO = "1999-1"


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# /v1/estudiantes/{estudianteId}/inscripciones
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_inscripciones_known_student(
    client: AsyncClient, estudiantes_token: str
):
    """EST-TEST-001 should have at least one enrollment."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/inscripciones",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_inscripciones_contains_required_fields(
    client: AsyncClient, estudiantes_token: str
):
    """Each enrollment record should contain the required fields."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/inscripciones",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    first = data[0]
    required_keys = {
        "codigoAsignatura", "nombreAsignatura", "codigoPrograma",
        "periodo", "creditos", "grupo", "docente", "estadoInscripcion",
    }
    assert required_keys.issubset(first.keys())


@pytest.mark.asyncio
async def test_get_inscripciones_filter_by_periodo(
    client: AsyncClient, estudiantes_token: str
):
    """Filtering by periodo should return only matching enrollments."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/inscripciones?periodo=2025-2",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert all(e["periodo"] == "2025-2" for e in data)


@pytest.mark.asyncio
async def test_get_inscripciones_filter_periodo_returns_empty_when_no_match(
    client: AsyncClient, estudiantes_token: str
):
    """Filtering by a period with no enrollments should return empty list."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/inscripciones?periodo=2020-1",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_get_inscripciones_unknown_student_returns_404(
    client: AsyncClient, estudiantes_token: str
):
    """Requesting enrollments for an unknown student should return 404."""
    response = await client.get(
        f"/v1/estudiantes/{INVALID_STUDENT}/inscripciones",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# /v1/estudiantes/{estudianteId}/calificaciones/{periodo}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_calificaciones_known_student_valid_period(
    client: AsyncClient, estudiantes_token: str
):
    """EST-TEST-001 should have grades for 2024-1."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/calificaciones/{VALID_PERIODO}",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_calificaciones_contains_required_fields(
    client: AsyncClient, estudiantes_token: str
):
    """Each grade record should contain the required fields."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/calificaciones/{VALID_PERIODO}",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    first = data[0]
    required_keys = {
        "codigoAsignatura", "nombreAsignatura", "periodo",
        "creditos", "notaFinal", "estado", "fechaRegistro", "docente",
    }
    assert required_keys.issubset(first.keys())


@pytest.mark.asyncio
async def test_get_calificaciones_nota_final_in_range(
    client: AsyncClient, estudiantes_token: str
):
    """notaFinal should be in the 0.0–5.0 range."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/calificaciones/{VALID_PERIODO}",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    for grade in data:
        assert 0.0 <= grade["notaFinal"] <= 5.0


@pytest.mark.asyncio
async def test_get_calificaciones_unknown_student_returns_404(
    client: AsyncClient, estudiantes_token: str
):
    """Requesting grades for an unknown student should return 404."""
    response = await client.get(
        f"/v1/estudiantes/{INVALID_STUDENT}/calificaciones/{VALID_PERIODO}",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_calificaciones_unknown_period_returns_404(
    client: AsyncClient, estudiantes_token: str
):
    """Requesting grades for a period that has no data should return 404."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/calificaciones/{INVALID_PERIODO}",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_calificaciones_2024_2(
    client: AsyncClient, estudiantes_token: str
):
    """EST-TEST-001 should also have grades for 2024-2."""
    response = await client.get(
        f"/v1/estudiantes/{TEST_STUDENT}/calificaciones/2024-2",
        headers=auth_header(estudiantes_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(g["periodo"] == "2024-2" for g in data)
