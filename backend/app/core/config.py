"""Application settings — validated at startup."""

from __future__ import annotations

import logging
from typing import Any

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database — defaults to SQLite for local dev without Docker
    DATABASE_URL: str = "sqlite+aiosqlite:///./asa_dev.db"
    DATABASE_URL_SYNC: str = "sqlite:///./asa_dev.db"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 2
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768

    # Per-user rate limits (requests per minute; 0 disables)
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 20
    RATE_LIMIT_PROCESSING_PER_MINUTE: int = 10

    # Storage
    STORAGE_BUCKET: str = "documents"

    # OCR limits
    OCR_LIMIT_PAGES_PER_DOC: int = 50
    OCR_LIMIT_PAGES_PER_USER_PER_DAY: int = 100
    OCR_FALLBACK_ENABLED: bool = False

    # App
    APP_NAME: str = "AI Study Assistant"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        validate_on_init = False


def validate_runtime_config(s: Settings | None = None) -> list[str]:
    """Return missing required settings; fail fast in production."""
    cfg = s or get_settings_instance()
    missing: list[str] = []
    if not cfg.SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not cfg.SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not cfg.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")

    if cfg.ENVIRONMENT.lower() in {"production", "prod"} and missing:
        raise RuntimeError(
            "Missing required production configuration: " + ", ".join(missing)
        )
    for name in missing:
        logger.warning("%s is not set; related features will be unavailable", name)
    return missing


def get_settings() -> Settings:
    return Settings()


_settings_instance: Settings | None = None


def get_settings_instance() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


class _LazySettings:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings_instance(), name)

    def __repr__(self) -> str:
        return f"<LazySettings: {get_settings_instance()}>"


settings = _LazySettings()  # type: ignore[assignment]
