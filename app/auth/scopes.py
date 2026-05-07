"""
OAuth 2.0 scope constants for the UPC Institutional API.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Scope constants
# ---------------------------------------------------------------------------
ACADEMICO_READ: str = "academico:read"
ESTUDIANTES_READ: str = "estudiantes:read"
DOCENTES_READ: str = "docentes:read"
ADMINISTRATIVO_READ: str = "administrativo:read"
SGDEA_READ: str = "sgdea:read"
SOPORTE_READ: str = "soporte:read"
EVENTOS_WRITE: str = "eventos:write"
ADMIN_READ: str = "admin:read"

# All known scopes (useful for documentation / validation)
ALL_SCOPES: list[str] = [
    ACADEMICO_READ,
    ESTUDIANTES_READ,
    DOCENTES_READ,
    ADMINISTRATIVO_READ,
    SGDEA_READ,
    SOPORTE_READ,
    EVENTOS_WRITE,
    ADMIN_READ,
]

# Human-readable descriptions (used in OpenAPI securitySchemes)
SCOPE_DESCRIPTIONS: dict[str, str] = {
    ACADEMICO_READ: "Read academic programs, subjects and periods",
    ESTUDIANTES_READ: "Read student enrollment and grade data",
    DOCENTES_READ: "Read faculty / teaching staff data",
    ADMINISTRATIVO_READ: "Read administrative data",
    SGDEA_READ: "Read SGDEA document management data",
    SOPORTE_READ: "Read support / helpdesk data",
    EVENTOS_WRITE: "Create and update institutional events",
    ADMIN_READ: "Read administrative API metrics and health details",
}
