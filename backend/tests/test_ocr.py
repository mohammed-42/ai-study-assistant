"""Tests for OCR providers and flagging logic."""

import pytest
from unittest.mock import MagicMock, patch

from app.ai.ocr import OcrResult, OcrQuality, flag_needs_review
from app.ai.gemini import GeminiOcrProvider
from app.ai.tesseract import TesseractOcrProvider


# --- flag_needs_review tests ---

@pytest.mark.asyncio
async def test_flag_needs_review_short_text():
    """Pages with very short output should be flagged."""
    result = OcrResult(text="Hi", quality=OcrQuality.HIGH)
    assert flag_needs_review(result) is True


@pytest.mark.asyncio
async def test_flag_needs_review_long_text_ok():
    """Long, clean text should not be flagged."""
    result = OcrResult(text="A" * 100, quality=OcrQuality.HIGH)
    assert flag_needs_review(result) is False


@pytest.mark.asyncio
async def test_flag_needs_review_low_confidence():
    """Low-confidence results should be flagged."""
    result = OcrResult(text="Some text", quality=OcrQuality.LOW, low_confidence=True)
    assert flag_needs_review(result) is True


@pytest.mark.asyncio
async def test_flag_needs_review_many_illegible():
    """Many [illegible] markers (>5) should trigger review flag."""
    text = "Hello [illegible] world [illegible] foo [illegible] bar [illegible] baz [illegible] qux [illegible] end"
    result = OcrResult(text=text, quality=OcrQuality.MEDIUM)
    assert flag_needs_review(result) is True


@pytest.mark.asyncio
async def test_flag_needs_review_few_illegible():
    """A couple [illegible] markers (<=5) should not trigger review flag."""
    # Must also be long enough to pass the min_length check
    text = "X" * 60 + " Hello [illegible] world"
    result = OcrResult(text=text, quality=OcrQuality.MEDIUM)
    assert flag_needs_review(result) is False


@pytest.mark.asyncio
async def test_flag_needs_review_custom_min_length():
    """Custom min_length threshold respected."""
    result = OcrResult(text="AB", quality=OcrQuality.HIGH)
    assert flag_needs_review(result, min_length=1) is False
    assert flag_needs_review(result, min_length=5) is True


# --- GeminiOcrProvider tests (mocked) ---

@pytest.mark.asyncio
async def test_gemini_provider_requires_api_key():
    """Gemini provider raises when GEMINI_API_KEY is not configured."""
    with patch("app.ai.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "your-gemini-api-key"
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            GeminiOcrProvider()


@pytest.mark.asyncio
async def test_gemini_provider_transcribe_success():
    """Successful transcription returns OcrResult with text."""
    mock_response = MagicMock()
    mock_response.text = "Transcribed text here"
    mock_response.candidates = [MagicMock(finish_reason=None)]

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    with patch("app.ai.gemini.genai.configure"), \
         patch("app.ai.gemini.genai.GenerativeModel", return_value=mock_model), \
         patch("app.ai.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        provider = GeminiOcrProvider()
        result = await provider.transcribe_page(b"fake-image-bytes", "image/jpeg")

    assert result.text == "Transcribed text here"
    assert result.low_confidence is False
    assert provider.name == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gemini_provider_transcribe_no_text():
    """When Gemini returns [NO_TEXT], result has empty text and LOW quality."""
    mock_response = MagicMock()
    mock_response.text = "[NO_TEXT]"
    mock_response.candidates = [MagicMock(finish_reason=None)]

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    with patch("app.ai.gemini.genai.configure"), \
         patch("app.ai.gemini.genai.GenerativeModel", return_value=mock_model), \
         patch("app.ai.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        provider = GeminiOcrProvider()
        result = await provider.transcribe_page(b"fake-image-bytes", "image/png")

    assert result.text == ""
    assert result.quality == OcrQuality.LOW
    assert "no_text_detected" in result.flags


@pytest.mark.asyncio
async def test_gemini_provider_transcribe_error_returns_low_conf():
    """When Gemini call fails, returns low-confidence empty result."""
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("network error")

    with patch("app.ai.gemini.genai.configure"), \
         patch("app.ai.gemini.genai.GenerativeModel", return_value=mock_model), \
         patch("app.ai.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        provider = GeminiOcrProvider()
        result = await provider.transcribe_page(b"fake-image-bytes", "image/jpeg")

    assert result.text == ""
    assert result.low_confidence is True
    assert len(result.flags) > 0


# --- TesseractOcrProvider tests ---

@pytest.mark.asyncio
async def test_tesseract_provider_not_available():
    """When pytesseract is not installed, returns low-quality empty result."""
    with patch.dict("sys.modules", {"pytesseract": None}):
        provider = TesseractOcrProvider()
        result = await provider.transcribe_page(b"fake-bytes", "image/jpeg")

    assert result.text == ""
    assert result.quality == OcrQuality.LOW
    assert "tesseract_not_available" in result.flags


@pytest.mark.asyncio
async def test_tesseract_provider_embed_not_supported():
    """Tesseract does not support embeddings."""
    provider = TesseractOcrProvider()
    with pytest.raises(NotImplementedError, match="embeddings"):
        await provider.embed_texts(["test"])
