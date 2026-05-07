"""
Application configuration via pydantic-settings.
All values can be overridden via environment variables or a .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://upc_user:upc_password@localhost:5432/upc_api"
    AUDIT_DATABASE_URL: str = "postgresql+asyncpg://upc_user:upc_password@localhost:5433/upc_audit"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379"

    # --- Keycloak / OIDC ---
    KEYCLOAK_JWKS_URL: str = (
        "https://auth.unicesar.edu.co/realms/upc/protocol/openid-connect/certs"
    )
    KEYCLOAK_ISSUER: str = "https://auth.unicesar.edu.co/realms/upc"
    API_AUDIENCE: str = "upc-api-institucional"

    # --- Application ---
    ENVIRONMENT: str = "sandbox"  # "production" | "sandbox"
    RATE_LIMIT_PER_MINUTE: int = 1000
    JWKS_CACHE_TTL_SECONDS: int = 3600


settings = Settings()
