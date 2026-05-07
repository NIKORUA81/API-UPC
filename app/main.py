"""
UPC API Institucional — application factory.

Responsibilities
----------------
- Create the FastAPI application instance.
- Register routers with /v1 prefix.
- Attach AuditMiddleware.
- Manage startup / shutdown lifecycle:
    * Open Redis connection.
    * Start audit writer background task.
    * Pre-load JWKS from Keycloak.
- Expose health endpoints (no authentication required).
- Apply SlowAPI rate limiting.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.audit.middleware import AuditMiddleware
from app.audit.writer import audit_writer_task
from app.auth.dependencies import require_scope
from app.auth.jwt_validator import force_refresh_jwks
from app.auth.scopes import ADMIN_READ
from app.config import settings
from app.db.database import AuditAsyncSessionLocal, audit_engine
from app.routers import academico, estudiantes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler."""

    # --- Startup ---
    logger.info("Starting UPC API Institucional (env=%s)", settings.ENVIRONMENT)

    # Connect to Redis
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
        )
        await redis_client.ping()
        app.state.redis = redis_client
        logger.info("Redis connection established: %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable on startup (non-fatal): %s", exc)
        app.state.redis = None

    # Pre-load JWKS
    try:
        await force_refresh_jwks()
        logger.info("JWKS loaded from Keycloak")
    except Exception as exc:
        logger.warning("Could not pre-load JWKS (non-fatal): %s", exc)

    # Start audit writer background task
    writer_task = None
    if app.state.redis is not None:
        session_factory: async_sessionmaker = AuditAsyncSessionLocal
        writer_task = asyncio.create_task(
            audit_writer_task(app.state.redis, session_factory),
            name="audit-writer",
        )
        app.state.audit_writer_task = writer_task
        logger.info("Audit writer background task started")
    else:
        app.state.audit_writer_task = None

    yield

    # --- Shutdown ---
    logger.info("Shutting down UPC API Institucional")

    if writer_task is not None and not writer_task.done():
        writer_task.cancel()
        try:
            await asyncio.wait_for(writer_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        logger.info("Audit writer task stopped")

    if redis_client is not None:
        await redis_client.aclose()
        logger.info("Redis connection closed")

    await audit_engine.dispose()
    logger.info("Audit DB engine disposed")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="UPC API Institucional — Módulo Académico",
        description=(
            "RESTful integration API for Universidad Popular del Cesar (UPC) institutional systems. "
            "Provides access to academic programmes, subjects, periods, student enrollments, "
            "and grades via OAuth 2.0 / JWT authentication."
        ),
        version="1.0.0",
        contact={
            "name": "Dirección de Tecnologías de la Información — UPC",
            "email": "api-soporte@unicesar.edu.co",
            "url": "https://www.unicesar.edu.co",
        },
        license_info={
            "name": "Proprietary",
            "url": "https://www.unicesar.edu.co/legal",
        },
        openapi_tags=[
            {
                "name": "Health",
                "description": "Service health and liveness probes (no authentication required)",
            },
            {
                "name": "Académico",
                "description": "Academic programmes, subjects and periods (scope: academico:read)",
            },
            {
                "name": "Estudiantes",
                "description": "Student enrollment and grade data (scope: estudiantes:read)",
            },
        ],
        lifespan=lifespan,
    )

    # --- Rate limiting ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Audit middleware (added last so it wraps everything) ---
    app.add_middleware(AuditMiddleware)

    # --- Routers ---
    app.include_router(academico.router, prefix="/v1")
    app.include_router(estudiantes.router, prefix="/v1")

    # --- Health endpoints ---
    _register_health_routes(app)

    return app


def _register_health_routes(app: FastAPI) -> None:
    """Register health check routes directly on the app instance."""

    @app.get(
        "/health",
        tags=["Health"],
        summary="Liveness probe",
        response_model=dict,
        responses={200: {"description": "Service is running"}},
    )
    async def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        }

    @app.get(
        "/health/detailed",
        tags=["Health"],
        summary="Detailed health check",
        response_model=dict,
        responses={
            200: {"description": "Detailed service status"},
            401: {"description": "Missing or invalid token"},
            403: {"description": "Insufficient scope"},
        },
    )
    async def health_detailed(
        request: Request,
        token_data: dict = Depends(require_scope(ADMIN_READ)),
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "status": "ok",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Redis check
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            try:
                await redis_client.ping()
                details["redis"] = "ok"
            except Exception as exc:
                details["redis"] = f"error: {exc}"
        else:
            details["redis"] = "unavailable"

        # Keycloak check (lightweight — just verify JWKS URL is reachable)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(settings.KEYCLOAK_JWKS_URL)
                details["keycloak"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
        except Exception as exc:
            details["keycloak"] = f"error: {exc}"

        return details


# ---------------------------------------------------------------------------
# Module-level app instance
# ---------------------------------------------------------------------------

app = create_app()
