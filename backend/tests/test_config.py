import logging

import pytest

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
