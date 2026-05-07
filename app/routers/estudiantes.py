"""
Students module router.

Endpoints
---------
GET /estudiantes/{estudianteId}/inscripciones               → List[Inscripcion]
GET /estudiantes/{estudianteId}/calificaciones/{periodo}    → List[CalificacionFinal]

All endpoints require the ``estudiantes:read`` scope.
Mock data is returned for the test student EST-TEST-001.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import require_scope
from app.auth.scopes import ESTUDIANTES_READ
from app.schemas.academico import CalificacionFinal, Inscripcion

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_INSCRIPCIONES: dict[str, list[dict[str, Any]]] = {
    "EST-TEST-001": [
        {
            "codigoAsignatura": "IS-301",
            "nombreAsignatura": "Ingeniería de Software I",
            "codigoPrograma": "ING-SIS-01",
            "periodo": "2025-2",
            "creditos": 3,
            "grupo": "A",
            "docente": "Dr. Carlos Pérez",
            "horario": "Lunes y Miércoles 08:00-10:00",
            "salon": "Bloque A - Aula 201",
            "estadoInscripcion": "ACTIVA",
        },
        {
            "codigoAsignatura": "IS-302",
            "nombreAsignatura": "Bases de Datos I",
            "codigoPrograma": "ING-SIS-01",
            "periodo": "2025-2",
            "creditos": 3,
            "grupo": "B",
            "docente": "Dra. Ana Martínez",
            "horario": "Martes y Jueves 10:00-12:00",
            "salon": "Bloque B - Lab. Sistemas 1",
            "estadoInscripcion": "ACTIVA",
        },
        {
            "codigoAsignatura": "IS-401",
            "nombreAsignatura": "Redes de Computadoras",
            "codigoPrograma": "ING-SIS-01",
            "periodo": "2025-2",
            "creditos": 3,
            "grupo": "A",
            "docente": "Ing. Luis Gómez",
            "horario": "Viernes 14:00-17:00",
            "salon": "Bloque C - Lab. Redes",
            "estadoInscripcion": "ACTIVA",
        },
        {
            "codigoAsignatura": "IS-201",
            "nombreAsignatura": "Programación Orientada a Objetos",
            "codigoPrograma": "ING-SIS-01",
            "periodo": "2024-2",
            "creditos": 3,
            "grupo": "A",
            "docente": "Dr. Carlos Pérez",
            "horario": "Lunes y Miércoles 10:00-12:00",
            "salon": "Bloque A - Aula 202",
            "estadoInscripcion": "ACTIVA",
        },
        {
            "codigoAsignatura": "IS-202",
            "nombreAsignatura": "Estructuras de Datos",
            "codigoPrograma": "ING-SIS-01",
            "periodo": "2024-2",
            "creditos": 3,
            "grupo": "A",
            "docente": "Ing. Pedro Rodríguez",
            "horario": "Martes y Jueves 08:00-10:00",
            "salon": "Bloque A - Aula 103",
            "estadoInscripcion": "ACTIVA",
        },
    ]
}

_CALIFICACIONES: dict[str, list[dict[str, Any]]] = {
    "EST-TEST-001": [
        {
            "codigoAsignatura": "IS-101",
            "nombreAsignatura": "Fundamentos de Programación",
            "periodo": "2024-1",
            "creditos": 3,
            "notaFinal": 4.2,
            "notaHabilitacion": None,
            "estado": "APROBADO",
            "fechaRegistro": date(2024, 6, 10),
            "docente": "Dra. María López",
        },
        {
            "codigoAsignatura": "IS-102",
            "nombreAsignatura": "Lógica Matemática",
            "periodo": "2024-1",
            "creditos": 3,
            "notaFinal": 3.5,
            "notaHabilitacion": None,
            "estado": "APROBADO",
            "fechaRegistro": date(2024, 6, 10),
            "docente": "Dr. Jorge Sánchez",
        },
        {
            "codigoAsignatura": "IS-201",
            "nombreAsignatura": "Programación Orientada a Objetos",
            "periodo": "2024-2",
            "creditos": 3,
            "notaFinal": 3.8,
            "notaHabilitacion": None,
            "estado": "APROBADO",
            "fechaRegistro": date(2024, 12, 10),
            "docente": "Dr. Carlos Pérez",
        },
        {
            "codigoAsignatura": "IS-202",
            "nombreAsignatura": "Estructuras de Datos",
            "periodo": "2024-2",
            "creditos": 3,
            "notaFinal": 2.8,
            "notaHabilitacion": 3.1,
            "estado": "APROBADO",
            "fechaRegistro": date(2024, 12, 10),
            "docente": "Ing. Pedro Rodríguez",
        },
    ]
}


def _not_found_response(student_id: str) -> dict:
    return {
        "error": "NOT_FOUND",
        "message": f"Student '{student_id}' not found.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requestId": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{estudianteId}/inscripciones",
    response_model=List[Inscripcion],
    summary="Obtener inscripciones del estudiante",
    description=(
        "Returns the enrollment list for the given student. "
        "Optionally filter by `periodo` (e.g. 2025-2)."
    ),
    responses={
        401: {"model": None, "description": "Missing or invalid Bearer token"},
        403: {"model": None, "description": "Insufficient scope"},
        404: {"model": None, "description": "Student not found"},
    },
)
async def get_inscripciones(
    estudianteId: str,
    periodo: Optional[str] = Query(None, description="Filter by period code (e.g. 2025-2)"),
    _token: dict = Depends(require_scope(ESTUDIANTES_READ)),
) -> List[Inscripcion]:
    if estudianteId not in _INSCRIPCIONES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_not_found_response(estudianteId),
        )

    records = _INSCRIPCIONES[estudianteId]
    if periodo:
        records = [r for r in records if r["periodo"] == periodo]

    return [Inscripcion(**r) for r in records]


@router.get(
    "/{estudianteId}/calificaciones/{periodo}",
    response_model=List[CalificacionFinal],
    summary="Obtener calificaciones por período",
    description=(
        "Returns the final grades for the given student in the specified academic period."
    ),
    responses={
        401: {"model": None, "description": "Missing or invalid Bearer token"},
        403: {"model": None, "description": "Insufficient scope"},
        404: {"model": None, "description": "Student not found or no grades for period"},
    },
)
async def get_calificaciones(
    estudianteId: str,
    periodo: str,
    _token: dict = Depends(require_scope(ESTUDIANTES_READ)),
) -> List[CalificacionFinal]:
    if estudianteId not in _CALIFICACIONES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_not_found_response(estudianteId),
        )

    all_grades = _CALIFICACIONES[estudianteId]
    grades_for_period = [g for g in all_grades if g["periodo"] == periodo]

    if not grades_for_period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NOT_FOUND",
                "message": f"No grades found for student '{estudianteId}' in period '{periodo}'.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requestId": str(uuid.uuid4()),
            },
        )

    return [CalificacionFinal(**g) for g in grades_for_period]
