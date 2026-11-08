"""Gemini access: shared google.genai client factory, generation and embedding."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import errors, types

from app.ai.ocr import (
    OcrAuthError,
    OcrBusyError,
    OcrProvider,
    OcrProviderError,
    OcrQuotaError,
    OcrResult,
    OcrQuality,
    classify_ocr_provider_error,
)
from app.core.config import settings
from app.core.resilience import call_with_retry

logger = logging.getLogger(__name__)

# Verbatim transcription prompt — instructs model to not invent/correct text
_TRANSCRIBE_PROMPT = """\
Transcribe the following image exactly as written. Follow these rules:
- Write verbatim — do not correct spelling, grammar, or punctuation.
- Preserve line breaks and layout as best as possible.
- If a word is unreadable, write [illegible] in its place.
- Do not add any commentary, summary, or interpretation — output ONLY the transcription.
- If the image contains no readable text, output: [NO_TEXT]
"""


def create_client(api_key: str) -> genai.Client:
    """Build a Gemini client from an explicit API key (no global configuration)."""
    if not api_key or api_key == "your-gemini-api-key":
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Set it in your .env file to use the Gemini provider."
        )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=int(settings.GEMINI_TIMEOUT_SECONDS * 1000)
        ),
    )


def classify_gemini_error(exc: BaseException | None) -> OcrProviderError:
    """Map google.genai exceptions to the existing typed provider errors."""
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, errors.APIError):
            code = getattr(current, "code", None)
            status = str(getattr(current, "status", "") or "").upper()
            if code == 429 or status == "RESOURCE_EXHAUSTED":
                return OcrQuotaError()
            if code in (401, 403) or status in (
                "UNAUTHENTICATED",
                "PERMISSION_DENIED",
            ):
                return OcrAuthError()
            if isinstance(code, int) and 500 <= code < 600:
                return OcrBusyError()
        current = current.__cause__
    return classify_ocr_provider_error(exc)


@dataclass(frozen=True)
class GeminiTextResult:
    """Text plus the provider finish reason reported by Gemini."""

    text: str
    finish_reason: str | None


def _finish_reason_name(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return None
    name = getattr(reason, "name", None)
    return name if isinstance(name, str) else str(reason)


async def generate_text(
    client: genai.Client,
    contents: Any,
    *,
    model: str,
    temperature: float,
    response_mime_type: str | None = None,
    max_output_tokens: int | None = None,
) -> GeminiTextResult:
    """Call generate_content with the shared timeout/retry wrapper."""
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type=response_mime_type,
        max_output_tokens=max_output_tokens,
    )
    response = await call_with_retry(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=config,
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
        retries=settings.GEMINI_MAX_RETRIES,
    )
    try:
        raw_text = response.text
    except Exception:
        raw_text = None
    return GeminiTextResult(
        text=raw_text.strip() if raw_text else "",
        finish_reason=_finish_reason_name(response),
    )


async def embed_text(
    client: genai.Client,
    text: str,
    *,
    model: str,
    output_dimensionality: int = 768,
) -> list[float]:
    """Embed one text, rejecting missing or all-zero vectors."""
    response = await call_with_retry(
        client.models.embed_content,
        model=model,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=output_dimensionality
        ),
        timeout=settings.GEMINI_TIMEOUT_SECONDS,
        retries=settings.GEMINI_MAX_RETRIES,
    )
    embeddings = getattr(response, "embeddings", None)
    if not embeddings:
        raise RuntimeError("Embedding response did not contain a vector")
    values = getattr(embeddings[0], "values", None)
    if not values:
        raise RuntimeError("Embedding response did not contain a vector")

    embedding = [float(value) for value in values]
    dim = output_dimensionality
    if len(embedding) < dim:
        embedding = embedding + [0.0] * (dim - len(embedding))
    elif len(embedding) > dim:
        embedding = embedding[:dim]
    if not any(abs(value) > 0.0 for value in embedding):
        raise RuntimeError("Embedding response was all zeros")
    return embedding


class GeminiOcrProvider(OcrProvider):
    """Uses Gemini multimodal to transcribe page images."""

    # Model name for embeddings (separate, used elsewhere)
    EMBEDDING_MODEL = settings.EMBEDDING_MODEL

    def __init__(self) -> None:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your-gemini-api-key":
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Set it in your .env file to use the Gemini OCR provider."
            )
        self._client = create_client(api_key)
        self._model_name = settings.GEMINI_MODEL

    @property
    def name(self) -> str:
        return self._model_name

    async def transcribe_page(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        """Transcribe a single page image using Gemini vision.

        Returns an OcrResult. On transient errors returns a result with
        low_confidence=True and empty text so the pipeline can mark the
        page for review rather than losing the page entirely.
        """
        try:
            blob = types.Blob(mime_type=mime_type, data=image_bytes)
            part = types.Part(inline_data=blob)

            result = await generate_text(
                self._client,
                [_TRANSCRIBE_PROMPT, part],
                model=self._model_name,
                temperature=0.0,
                max_output_tokens=2048,
            )

            text = result.text

            quality = OcrQuality.HIGH
            flags: list[str] = []
            low_conf = False

            if "[NO_TEXT]" in text.upper():
                text = ""
                quality = OcrQuality.LOW
                flags.append("no_text_detected")
                low_conf = True
            elif result.finish_reason not in (None, "STOP"):
                flags.append(f"finish_reason={result.finish_reason}")
                low_conf = True

            if low_conf:
                quality = OcrQuality.LOW
            elif len(flags) > 0:
                quality = OcrQuality.MEDIUM

            return OcrResult(
                text=text,
                quality=quality,
                flags=flags,
                low_confidence=low_conf,
            )

        except Exception as exc:
            logger.warning("Gemini OCR failed for page: %s", type(exc).__name__)
            raise classify_gemini_error(exc) from exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed texts; raise instead of returning zero vectors on failure."""
        model_name = settings.EMBEDDING_MODEL or self.EMBEDDING_MODEL
        dim = settings.EMBEDDING_DIM or 768
        if not texts:
            return []

        vectors: list[list[float]] = []
        for text in texts:
            if not text or not text.strip():
                raise ValueError("Cannot embed empty text")
            try:
                embedding = await embed_text(
                    self._client,
                    text,
                    model=model_name,
                    output_dimensionality=dim,
                )
            except Exception as exc:
                logger.warning("Gemini embedding failed: %s", type(exc).__name__)
                raise
            vectors.append(embedding)
        return vectors
