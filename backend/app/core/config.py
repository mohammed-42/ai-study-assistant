"""Application settings — validated at startup."""

from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — defaults to SQLite for local dev without Docker
    DATABASE_URL: str = "sqlite+aiosqlite:///./asa_dev.db"
    DATABASE_URL_SYNC: str = "sqlite:///./asa_dev.db"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWKS_URL: str = "https://api.supabase.com/auth/v1/keys"

    # Gemini
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_DIM: int = 768

    # Storage
    STORAGE_BUCKET: str = "documents"

    # OCR limits
    OCR_LIMIT_PAGES_PER_DOC: int = 50
    OCR_LIMIT_PAGES_PER_USER_PER_DAY: int = 100
    OCR_FALLBACK_ENABLED: bool = False

    # App
    APP_NAME: str = "AI Study Assistant"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        validate_on_init = False


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
