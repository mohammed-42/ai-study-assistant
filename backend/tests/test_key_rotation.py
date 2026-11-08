"""Gemini API-key rotation and shared cooldown behavior (mocked)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.genai import errors

from app.ai import gemini
from app.ai.gemini import embed_text, generate_text
from app.ai.ocr import OcrAuthError, OcrQuotaError


def _settings(keys: str, single: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        GEMINI_API_KEYS=keys,
        GEMINI_API_KEY=single,
        GEMINI_MODEL="test-model",
        GEMINI_TIMEOUT_SECONDS=1,
        GEMINI_MAX_RETRIES=0,
        EMBEDDING_MODEL="test-embedding-model",
        EMBEDDING_DIM=768,
    )


def _text_response(text: str = "served") -> MagicMock:
    response = MagicMock()
    response.text = text
    response.candidates = [MagicMock(finish_reason=None)]
    return response


def _embedding_response(dim: int = 768) -> MagicMock:
    return MagicMock(embeddings=[MagicMock(values=[0.25] * dim)])


def _quota_error(period: str = "minute") -> errors.ClientError:
    quota_id = (
        "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
        if period == "minute"
        else "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
    )
    return errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "message": "You exceeded your current quota",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": quota_id}],
                    }
                ],
            }
        },
    )


def _patch_clients(monkeypatch, clients: dict[str, MagicMock]) -> list[str]:
    created: list[str] = []

    def fake_create_client(api_key: str):
        created.append(api_key)
        return clients[api_key]

    monkeypatch.setattr(gemini, "create_client", fake_create_client)
    return created


@pytest.mark.asyncio
async def test_quota_rotates_to_next_key(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = _quota_error("minute")
    second = MagicMock()
    second.models.generate_content.return_value = _text_response()

    created = _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    result = await generate_text("prompt", model="test-model", temperature=0.0)

    assert result.text == "served"
    assert created == ["key-one", "key-two"]
    assert first.models.generate_content.call_count == 1
    assert second.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_next_call_skips_cooling_key(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = _quota_error("minute")
    second = MagicMock()
    second.models.generate_content.return_value = _text_response()

    _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    await generate_text("prompt", model="test-model", temperature=0.0)
    first.models.generate_content.reset_mock()
    second.models.generate_content.reset_mock()

    await generate_text("prompt", model="test-model", temperature=0.0)

    assert first.models.generate_content.call_count == 0
    assert second.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_minute_cooldown_expires(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(gemini, "_monotonic", lambda: clock["now"])
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = [
        _quota_error("minute"),
        _text_response("key-one recovered"),
    ]
    second = MagicMock()
    second.models.generate_content.return_value = _text_response()

    created = _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    await generate_text("prompt", model="test-model", temperature=0.0)
    clock["now"] += 61
    result = await generate_text("prompt", model="test-model", temperature=0.0)

    assert result.text == "key-one recovered"
    assert created == ["key-one", "key-two"]
    assert first.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_all_keys_quota_raises_typed_error(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = _quota_error("minute")
    second = MagicMock()
    second.models.generate_content.side_effect = _quota_error("minute")

    _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    with pytest.raises(OcrQuotaError):
        await generate_text("prompt", model="test-model", temperature=0.0)


@pytest.mark.asyncio
async def test_auth_error_does_not_rotate(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = errors.ClientError(
        401,
        {
            "error": {
                "code": 401,
                "message": "API key not valid",
                "status": "UNAUTHENTICATED",
            }
        },
    )
    second = MagicMock()
    second.models.generate_content.return_value = _text_response()

    created = _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    with pytest.raises(OcrAuthError):
        await generate_text("prompt", model="test-model", temperature=0.0)

    assert created == ["key-one"]
    assert second.models.generate_content.call_count == 0


@pytest.mark.asyncio
async def test_server_error_rotates_with_short_cooldown(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.generate_content.side_effect = errors.ServerError(
        500,
        {
            "error": {
                "code": 500,
                "message": "backend busy",
                "status": "INTERNAL",
            }
        },
    )
    second = MagicMock()
    second.models.generate_content.return_value = _text_response()

    _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    result = await generate_text("prompt", model="test-model", temperature=0.0)

    assert result.text == "served"
    assert first.models.generate_content.call_count == 1
    assert second.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_embedding_rotates_to_next_key(monkeypatch):
    monkeypatch.setattr(gemini, "settings", _settings("key-one,key-two"))
    first = MagicMock()
    first.models.embed_content.side_effect = _quota_error("minute")
    second = MagicMock()
    second.models.embed_content.return_value = _embedding_response(768)

    _patch_clients(monkeypatch, {"key-one": first, "key-two": second})

    vector = await embed_text(
        "hello", model="test-embedding-model", output_dimensionality=768
    )

    assert len(vector) == 768
    assert second.models.embed_content.call_count == 1


@pytest.mark.asyncio
async def test_no_key_in_logs_or_errors(monkeypatch, caplog):
    secret_one = "SECRET-KEY-ONE"
    secret_two = "SECRET-KEY-TWO"
    monkeypatch.setattr(
        gemini, "settings", _settings(f"{secret_one},{secret_two}")
    )
    first = MagicMock()
    first.models.generate_content.side_effect = _quota_error("minute")
    second = MagicMock()
    second.models.generate_content.side_effect = _quota_error("minute")

    _patch_clients(monkeypatch, {secret_one: first, secret_two: second})

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(OcrQuotaError) as excinfo:
            await generate_text("prompt", model="test-model", temperature=0.0)

    output = caplog.text + str(excinfo.value)
    assert secret_one not in output
    assert secret_two not in output
