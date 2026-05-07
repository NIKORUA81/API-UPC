"""
SQLAlchemy async engine and session factory setup.

Two engines are created:
- ``engine``         → main application database (upc_api)
- ``audit_engine``   → dedicated audit database (upc_audit)

Both use the asyncpg driver.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ---------------------------------------------------------------------------
# Main application database
# ---------------------------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ---------------------------------------------------------------------------
# Audit database
# ---------------------------------------------------------------------------

audit_engine: AsyncEngine = create_async_engine(
    settings.AUDIT_DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

AuditAsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    audit_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ---------------------------------------------------------------------------
# Shared declarative base for the main database
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for main application models."""


# ---------------------------------------------------------------------------
# Dependency helper
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that yields an async session for the main DB."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_audit_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency that yields an async session for the audit DB."""
    async with AuditAsyncSessionLocal() as session:
        yield session
