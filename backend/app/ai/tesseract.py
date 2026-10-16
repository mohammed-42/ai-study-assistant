"""Optional Tesseract OCR fallback — printed text only."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.ai.ocr import OcrProvider, OcrResult, OcrQuality

if TYPE_CHECKING:
    pass  # pytesseract not imported at module level to avoid hard dependency

logger = logging.getLogger(__name__)


class TesseractOcrProvider(OcrProvider):
    """Fallback OCR using Tesseract — best for clean printed text only."""

    NAME = "tesseract"

    @property
    def name(self) -> str:
        return self.NAME

    async def transcribe_page(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        try:
            import pytesseract  # type: ignore
            from PIL import Image
            import io
        except ImportError:
            logger.warning("TesseractOcrProvider used but pytesseract/PIL not installed")
            return OcrResult(
                text="",
                quality=OcrQuality.LOW,
                flags=["tesseract_not_available"],
                low_confidence=True,
            )

        try:
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img).strip()
            # Tesseract provides a confidence score per word; we approximate
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confidences = [c for c in data["conf"] if c > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            quality = OcrQuality.HIGH if avg_conf > 80 else (OcrQuality.MEDIUM if avg_conf > 50 else OcrQuality.LOW)
            flags: list[str] = []
            if avg_conf < 50:
                flags.append("low_confidence_tesseract")

            return OcrResult(
                text=text,
                quality=quality,
                flags=flags,
                low_confidence=avg_conf < 50,
                metadata={"avg_confidence": avg_conf},
            )
        except Exception as exc:
            logger.warning("Tesseract OCR failed: %s", exc)
            return OcrResult(
                text="",
                quality=OcrQuality.LOW,
                flags=[f"error:{type(exc).__name__}"],
                low_confidence=True,
            )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Tesseract has no embedding capability — delegates to the caller."""
        raise NotImplementedError(
            "TesseractOcrProvider does not support embeddings. "
            "Use GeminiOcrProvider for embeddings."
        )
