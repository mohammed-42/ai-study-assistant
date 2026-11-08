import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, validate_runtime_config


def _settings(**overrides):
    base = dict(
        ENVIRONMENT="development",
        SUPABASE_URL="",
        SUPABASE_SERVICE_ROLE_KEY="",
        GEMINI_API_KEY="",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_missing_config_raises():
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        validate_runtime_config(_settings(ENVIRONMENT="production"))


def test_development_missing_config_warns(caplog):
    with caplog.at_level(logging.WARNING):
        missing = validate_runtime_config(_settings())

    assert "SUPABASE_URL" in missing
    assert "SUPABASE_SERVICE_ROLE_KEY" in missing
    assert "GEMINI_API_KEY" in missing
    assert any("GEMINI_API_KEY" in record.message for record in caplog.records)


def test_complete_config_has_no_missing_values():
    missing = validate_runtime_config(
        _settings(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="service-role",
            GEMINI_API_KEY="gemini-key",
        )
    )
    assert missing == []


def test_chunk_settings_defaults():
    cfg = _settings()
    assert cfg.CHUNK_TARGET_TOKENS == 350
    assert cfg.CHUNK_OVERLAP_TOKENS == 60


def test_chunk_overlap_must_be_less_than_target():
    with pytest.raises(ValidationError, match="CHUNK_OVERLAP_TOKENS"):
        _settings(CHUNK_TARGET_TOKENS=100, CHUNK_OVERLAP_TOKENS=100)


def _production_settings(**overrides):
    base = dict(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/app",
        DATABASE_URL_SYNC="postgresql://user:pass@db:5432/app",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon-key",
        SUPABASE_JWKS_URL="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        SUPABASE_SERVICE_ROLE_KEY="service-role",
        GEMINI_API_KEY="gemini-key",
        ALLOWED_ORIGINS="https://app.example.com",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_valid_config_passes():
    assert validate_runtime_config(_production_settings()) == []


def test_production_rejects_wildcard_cors():
    with pytest.raises(RuntimeError, match="wildcard"):
        validate_runtime_config(_production_settings(ALLOWED_ORIGINS="https://app.example.com,*"))


def test_production_rejects_empty_cors():
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        validate_runtime_config(_production_settings(ALLOWED_ORIGINS=""))


def test_production_rejects_missing_required_setting():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        validate_runtime_config(_production_settings(GEMINI_API_KEY=""))


def test_production_rejects_debug_enabled():
    with pytest.raises(RuntimeError, match="DEBUG"):
        validate_runtime_config(_production_settings(DEBUG=True))
