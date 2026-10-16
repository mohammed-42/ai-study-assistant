"""Gemini multimodal vision OCR provider."""

from __future__ import annotations

import base64
import logging
from typing import Any

import google.generativeai as genai
from google.generativeai import protos
from google.generativeai.types import answer_types

from app.ai.ocr import OcrProvider, OcrResult, OcrQuality
from app.core.config import settings

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


class GeminiOcrProvider(OcrProvider):
    """Uses Gemini 2.0 Flash multimodal to transcribe page images."""

    # Model name for transcription
    MODEL = "gemini-2.0-flash"
    # Model name for embeddings (separate, used elsewhere)
    EMBEDDING_MODEL = "text-embedding-004"

    def __init__(self) -> None:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == "your-gemini-api-key":
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Set it in your .env file to use the Gemini OCR provider."
            )
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.MODEL)

    @property
    def name(self) -> str:
        return self.MODEL

    async def transcribe_page(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        """Transcribe a single page image using Gemini vision.

        Returns an OcrResult. On transient errors returns a result with
        low_confidence=True and empty text so the pipeline can mark the
        page for review rather than losing the page entirely.
        """
        try:
            blob = protos.Blob(mime_type=mime_type, data=image_bytes)
            part = protos.Part(inline_data=blob)

            response = self._model.generate_content(
                [_TRANSCRIBE_PROMPT, part],
                generation_config={"max_output_tokens": 2048, "temperature": 0.0},
            )

            text = response.text.strip() if response.text else ""

            quality = OcrQuality.HIGH
            flags: list[str] = []
            low_conf = False

            if "[NO_TEXT]" in text.upper():
                text = ""
                quality = OcrQuality.LOW
                flags.append("no_text_detected")
                low_conf = True
            elif response.candidates and response.candidates[0].finish_reason not in (
                answer_types.FinishReason.STOP,
                None,
            ):
                flags.append(f"finish_reason={response.candidates[0].finish_reason}")
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
            logger.warning("Gemini OCR failed for page: %s", exc)
            return OcrResult(
                text="",
                quality=OcrQuality.LOW,
                flags=[f"error:{type(exc).__name__}"],
                low_confidence=True,
            )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed texts using the configured embedding model."""
        model_name = settings.EMBEDDING_MODEL or self.EMBEDDING_MODEL
        dim = settings.EMBEDDING_DIM or 768
        vectors: list[list[float]] = []
        for text in texts:
            if not text or not text.strip():
                vectors.append([0.0] * dim)
                continue
            try:
                response = genai.embed_content(model=f"models/{model_name}", content=text)
                embedding = response.get("embedding", [0.0] * dim)
                # Pad or truncate to expected dimension
                if len(embedding) < dim:
                    embedding = embedding + [0.0] * (dim - len(embedding))
                elif len(embedding) > dim:
                    embedding = embedding[:dim]
                vectors.append(embedding)
            except Exception as exc:
                logger.warning("Embedding failed for chunk: %s", exc)
                vectors.append([0.0] * dim)
        return vectors
