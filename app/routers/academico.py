"""
Academic module router.

Endpoints
---------
GET /academico/programas                               → PaginatedResponse[Programa]
GET /academico/programas/{codigoPrograma}/asignaturas  → List[Asignatura]
GET /academico/periodos                                → List[Periodo]

All endpoints require the ``academico:read`` scope.
Mock data is returned (no live ACADEMUSOFT connection).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_scope
from app.auth.scopes import ACADEMICO_READ
from app.schemas.academico import Asignatura, PaginatedResponse, Periodo, Programa

router = APIRouter(prefix="/academico", tags=["Académico"])

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_PROGRAMAS: list[dict[str, Any]] = [
    {
        "codigoPrograma": "ING-SIS-01",
        "nombrePrograma": "Ingeniería de Sistemas",
        "facultad": "Facultad de Ingenierías y Tecnologías",
        "nivel": "PREGRADO",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 160,
        "duracionSemestres": 10,
        "registroSnies": "10943",
        "acreditado": True,
    },
    {
        "codigoPrograma": "ING-ELC-02",
        "nombrePrograma": "Ingeniería Electrónica",
        "facultad": "Facultad de Ingenierías y Tecnologías",
        "nivel": "PREGRADO",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 156,
        "duracionSemestres": 10,
        "registroSnies": "10944",
        "acreditado": False,
    },
    {
        "codigoPrograma": "ADM-EMP-01",
        "nombrePrograma": "Administración de Empresas",
        "facultad": "Facultad de Ciencias Administrativas, Contables y Económicas",
        "nivel": "PREGRADO",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 148,
        "duracionSemestres": 10,
        "registroSnies": "10111",
        "acreditado": True,
    },
    {
        "codigoPrograma": "DER-01",
        "nombrePrograma": "Derecho",
        "facultad": "Facultad de Derecho, Ciencias Políticas y Sociales",
        "nivel": "PREGRADO",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 152,
        "duracionSemestres": 10,
        "registroSnies": "10222",
        "acreditado": True,
    },
    {
        "codigoPrograma": "ENF-01",
        "nombrePrograma": "Enfermería",
        "facultad": "Facultad de Ciencias de la Salud",
        "nivel": "PREGRADO",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 162,
        "duracionSemestres": 10,
        "registroSnies": "10333",
        "acreditado": False,
    },
    {
        "codigoPrograma": "CONT-01",
        "nombrePrograma": "Contaduría Pública",
        "facultad": "Facultad de Ciencias Administrativas, Contables y Económicas",
        "nivel": "PREGRADO",
        "modalidad": "DISTANCIA",
        "creditosTotales": 144,
        "duracionSemestres": 10,
        "registroSnies": "10444",
        "acreditado": False,
    },
    {
        "codigoPrograma": "ESP-GTIC-01",
        "nombrePrograma": "Especialización en Gestión de TIC",
        "facultad": "Facultad de Ingenierías y Tecnologías",
        "nivel": "ESPECIALIZACION",
        "modalidad": "VIRTUAL",
        "creditosTotales": 30,
        "duracionSemestres": 2,
        "registroSnies": "20001",
        "acreditado": False,
    },
    {
        "codigoPrograma": "MAE-EDUC-01",
        "nombrePrograma": "Maestría en Educación",
        "facultad": "Facultad de Educación",
        "nivel": "MAESTRIA",
        "modalidad": "PRESENCIAL",
        "creditosTotales": 60,
        "duracionSemestres": 4,
        "registroSnies": "30001",
        "acreditado": False,
    },
]

_ASIGNATURAS_BY_PROGRAMA: dict[str, list[dict[str, Any]]] = {
    "ING-SIS-01": [
        {
            "codigoAsignatura": "IS-101",
            "nombreAsignatura": "Fundamentos de Programación",
            "creditos": 3,
            "semestre": 1,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Ciencias de la Computación",
            "horasSemanales": 4,
            "prerequisitos": [],
        },
        {
            "codigoAsignatura": "IS-102",
            "nombreAsignatura": "Lógica Matemática",
            "creditos": 3,
            "semestre": 1,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Matemáticas",
            "horasSemanales": 3,
            "prerequisitos": [],
        },
        {
            "codigoAsignatura": "IS-201",
            "nombreAsignatura": "Programación Orientada a Objetos",
            "creditos": 3,
            "semestre": 2,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Ciencias de la Computación",
            "horasSemanales": 4,
            "prerequisitos": ["IS-101"],
        },
        {
            "codigoAsignatura": "IS-202",
            "nombreAsignatura": "Estructuras de Datos",
            "creditos": 3,
            "semestre": 2,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Ciencias de la Computación",
            "horasSemanales": 4,
            "prerequisitos": ["IS-101"],
        },
        {
            "codigoAsignatura": "IS-301",
            "nombreAsignatura": "Ingeniería de Software I",
            "creditos": 3,
            "semestre": 3,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Ingeniería de Software",
            "horasSemanales": 4,
            "prerequisitos": ["IS-201"],
        },
        {
            "codigoAsignatura": "IS-302",
            "nombreAsignatura": "Bases de Datos I",
            "creditos": 3,
            "semestre": 3,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Bases de Datos",
            "horasSemanales": 4,
            "prerequisitos": ["IS-202"],
        },
        {
            "codigoAsignatura": "IS-401",
            "nombreAsignatura": "Redes de Computadoras",
            "creditos": 3,
            "semestre": 4,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Redes y Comunicaciones",
            "horasSemanales": 3,
            "prerequisitos": ["IS-201"],
        },
        {
            "codigoAsignatura": "IS-402",
            "nombreAsignatura": "Ingeniería de Software II",
            "creditos": 3,
            "semestre": 4,
            "tipoAsignatura": "OBLIGATORIA",
            "areaFormacion": "Ingeniería de Software",
            "horasSemanales": 4,
            "prerequisitos": ["IS-301"],
        },
        {
            "codigoAsignatura": "IS-EL-01",
            "nombreAsignatura": "Inteligencia Artificial",
            "creditos": 3,
            "semestre": 7,
            "tipoAsignatura": "ELECTIVA",
            "areaFormacion": "Ciencias de la Computación",
            "horasSemanales": 3,
            "prerequisitos": ["IS-202"],
        },
        {
            "codigoAsignatura": "IS-EL-02",
            "nombreAsignatura": "Seguridad Informática",
            "creditos": 3,
            "semestre": 8,
            "tipoAsignatura": "ELECTIVA",
            "areaFormacion": "Seguridad",
            "horasSemanales": 3,
            "prerequisitos": ["IS-401"],
        },
    ],
}

_PERIODOS: list[dict[str, Any]] = [
    {
        "codigoPeriodo": "2024-1",
        "nombrePeriodo": "Primer Semestre 2024",
        "fechaInicio": date(2024, 1, 29),
        "fechaFin": date(2024, 6, 8),
        "activo": False,
        "periodoMatriculas": False,
    },
    {
        "codigoPeriodo": "2024-2",
        "nombrePeriodo": "Segundo Semestre 2024",
        "fechaInicio": date(2024, 7, 22),
        "fechaFin": date(2024, 12, 7),
        "activo": False,
        "periodoMatriculas": False,
    },
    {
        "codigoPeriodo": "2025-1",
        "nombrePeriodo": "Primer Semestre 2025",
        "fechaInicio": date(2025, 1, 27),
        "fechaFin": date(2025, 6, 7),
        "activo": False,
        "periodoMatriculas": False,
    },
    {
        "codigoPeriodo": "2025-2",
        "nombrePeriodo": "Segundo Semestre 2025",
        "fechaInicio": date(2025, 7, 21),
        "fechaFin": date(2025, 12, 6),
        "activo": True,
        "periodoMatriculas": False,
    },
    {
        "codigoPeriodo": "2026-1",
        "nombrePeriodo": "Primer Semestre 2026",
        "fechaInicio": date(2026, 1, 26),
        "fechaFin": date(2026, 6, 6),
        "activo": True,
        "periodoMatriculas": True,
    },
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/programas",
    response_model=PaginatedResponse[Programa],
    summary="Listar programas académicos",
    description=(
        "Returns a paginated list of all academic programmes offered by UPC. "
        "Optionally filter by `nivel` (PREGRADO, POSGRADO, etc.) and `modalidad` "
        "(PRESENCIAL, VIRTUAL, DISTANCIA)."
    ),
    responses={
        401: {"model": None, "description": "Missing or invalid Bearer token"},
        403: {"model": None, "description": "Insufficient scope"},
    },
)
async def list_programas(
    nivel: Optional[str] = Query(None, description="Filter by academic level"),
    modalidad: Optional[str] = Query(None, description="Filter by delivery mode"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Records per page"),
    _token: dict = Depends(require_scope(ACADEMICO_READ)),
) -> PaginatedResponse[Programa]:
    filtered = _PROGRAMAS

    if nivel:
        filtered = [p for p in filtered if p["nivel"].upper() == nivel.upper()]
    if modalidad:
        filtered = [p for p in filtered if p["modalidad"].upper() == modalidad.upper()]

    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    page_data = filtered[start:end]

    return PaginatedResponse[Programa](
        data=[Programa(**p) for p in page_data],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/programas/{codigoPrograma}/asignaturas",
    response_model=List[Asignatura],
    summary="Listar asignaturas de un programa",
    description=(
        "Returns all subjects belonging to the given programme. "
        "Optionally filter by `semestre` (1-12)."
    ),
    responses={
        401: {"model": None, "description": "Missing or invalid Bearer token"},
        403: {"model": None, "description": "Insufficient scope"},
        404: {"model": None, "description": "Programme not found"},
    },
)
async def list_asignaturas(
    codigoPrograma: str,
    semestre: Optional[int] = Query(None, ge=1, le=12, description="Filter by semester"),
    _token: dict = Depends(require_scope(ACADEMICO_READ)),
) -> List[Asignatura]:
    # Check programme exists
    known_codes = {p["codigoPrograma"] for p in _PROGRAMAS}
    if codigoPrograma not in known_codes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"Programme '{codigoPrograma}' not found.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requestId": str(uuid.uuid4()),
            },
        )

    subjects = _ASIGNATURAS_BY_PROGRAMA.get(codigoPrograma, [])

    if semestre is not None:
        subjects = [s for s in subjects if s["semestre"] == semestre]

    return [Asignatura(**s) for s in subjects]


@router.get(
    "/periodos",
    response_model=List[Periodo],
    summary="Listar períodos académicos",
    description="Returns academic periods. Use `soloActivos=true` (default) to get only active periods.",
    responses={
        401: {"model": None, "description": "Missing or invalid Bearer token"},
        403: {"model": None, "description": "Insufficient scope"},
    },
)
async def list_periodos(
    soloActivos: bool = Query(True, description="Return only active periods"),
    _token: dict = Depends(require_scope(ACADEMICO_READ)),
) -> List[Periodo]:
    periods = _PERIODOS
    if soloActivos:
        periods = [p for p in periods if p["activo"]]
    return [Periodo(**p) for p in periods]
