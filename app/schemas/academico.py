"""
Pydantic schemas for the UPC Institutional API.

Covers:
- Programa (academic program)
- Asignatura (course / subject)
- Periodo (academic period)
- Inscripcion (enrollment record)
- CalificacionFinal (final grade)
- ErrorResponse
- PaginatedResponse (generic)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

DataT = TypeVar("DataT")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Wrapper for paginated list endpoints."""

    data: List[DataT]
    total: int = Field(..., description="Total number of records matching the filter")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    limit: int = Field(..., ge=1, le=100, description="Number of records per page")


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str = Field(..., example="UNAUTHORIZED", description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    timestamp: datetime = Field(..., description="UTC timestamp of the error")
    requestId: str = Field(..., example="3fa85f64-5717-4562-b3fc-2c963f66afa6")


# ---------------------------------------------------------------------------
# Academic entities
# ---------------------------------------------------------------------------

class Programa(BaseModel):
    """Academic degree programme offered by UPC."""

    codigoPrograma: str = Field(
        ...,
        example="ING-SIS-01",
        description="Unique programme code (e.g. ING-SIS-01)",
    )
    nombrePrograma: str = Field(
        ...,
        example="Ingeniería de Sistemas",
        description="Full official name of the programme",
    )
    facultad: str = Field(
        ...,
        example="Facultad de Ingenierías y Tecnologías",
        description="Faculty that owns the programme",
    )
    nivel: str = Field(
        ...,
        example="PREGRADO",
        description="Academic level: PREGRADO, POSGRADO, ESPECIALIZACION, MAESTRIA",
    )
    modalidad: str = Field(
        ...,
        example="PRESENCIAL",
        description="Delivery mode: PRESENCIAL, VIRTUAL, DISTANCIA",
    )
    creditosTotales: int = Field(
        ...,
        example=160,
        description="Total credit hours required to graduate",
    )
    duracionSemestres: int = Field(
        ...,
        example=10,
        description="Programme duration in semesters",
    )
    registroSnies: Optional[str] = Field(
        None,
        example="10943",
        description="MEN / SNIES registration number",
    )
    acreditado: bool = Field(
        ...,
        example=True,
        description="Whether the programme holds a high-quality accreditation",
    )

    model_config = {"from_attributes": True}


class Asignatura(BaseModel):
    """A course / subject within an academic programme."""

    codigoAsignatura: str = Field(
        ...,
        example="IS-301",
        description="Unique subject code",
    )
    nombreAsignatura: str = Field(
        ...,
        example="Ingeniería de Software I",
        description="Full subject name",
    )
    creditos: int = Field(
        ...,
        example=3,
        description="Credit hours",
    )
    semestre: int = Field(
        ...,
        ge=1,
        le=12,
        example=3,
        description="Recommended semester (1-12)",
    )
    tipoAsignatura: str = Field(
        ...,
        example="OBLIGATORIA",
        description="OBLIGATORIA or ELECTIVA",
    )
    areaFormacion: str = Field(
        ...,
        example="Ciencias de la Computación",
        description="Knowledge area",
    )
    horasSemanales: int = Field(
        ...,
        example=4,
        description="Weekly contact hours",
    )
    prerequisitos: List[str] = Field(
        default_factory=list,
        example=["IS-201"],
        description="List of prerequisite subject codes",
    )

    model_config = {"from_attributes": True}


class Periodo(BaseModel):
    """Academic period (semester)."""

    codigoPeriodo: str = Field(
        ...,
        example="2024-1",
        description="Period code in YYYY-N format",
    )
    nombrePeriodo: str = Field(
        ...,
        example="Primer Semestre 2024",
        description="Human-readable period name",
    )
    fechaInicio: date = Field(
        ...,
        example="2024-01-29",
        description="Period start date",
    )
    fechaFin: date = Field(
        ...,
        example="2024-06-08",
        description="Period end date",
    )
    activo: bool = Field(
        ...,
        description="Whether this period is currently active",
    )
    periodoMatriculas: bool = Field(
        ...,
        description="Whether enrollment is currently open for this period",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Student entities
# ---------------------------------------------------------------------------

class Inscripcion(BaseModel):
    """A student's enrollment in a course for a given period."""

    codigoAsignatura: str = Field(..., example="IS-301")
    nombreAsignatura: str = Field(..., example="Ingeniería de Software I")
    codigoPrograma: str = Field(..., example="ING-SIS-01")
    periodo: str = Field(..., example="2024-1")
    creditos: int = Field(..., example=3)
    grupo: str = Field(..., example="A")
    docente: str = Field(..., example="Dr. Carlos Pérez")
    horario: str = Field(..., example="Lunes y Miércoles 08:00-10:00")
    salon: str = Field(..., example="Bloque A - Aula 201")
    estadoInscripcion: str = Field(
        ...,
        example="ACTIVA",
        description="ACTIVA, CANCELADA, RETIRADA",
    )

    model_config = {"from_attributes": True}


class CalificacionFinal(BaseModel):
    """Final grade record for a student in a course/period."""

    codigoAsignatura: str = Field(..., example="IS-201")
    nombreAsignatura: str = Field(..., example="Programación Orientada a Objetos")
    periodo: str = Field(..., example="2023-2")
    creditos: int = Field(..., example=3)
    notaFinal: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        example=3.8,
        description="Final grade on a 0.0–5.0 scale",
    )
    notaHabilitacion: Optional[float] = Field(
        None,
        ge=0.0,
        le=5.0,
        description="Make-up / habilitación grade, if applicable",
    )
    estado: str = Field(
        ...,
        example="APROBADO",
        description="APROBADO, REPROBADO, CANCELADO",
    )
    fechaRegistro: date = Field(..., example="2023-12-10")
    docente: str = Field(..., example="Dr. Carlos Pérez")

    model_config = {"from_attributes": True}
