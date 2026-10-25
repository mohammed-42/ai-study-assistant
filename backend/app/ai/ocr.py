"""OCR provider interface and result types."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class OcrQuality(enum.Enum):
    """Signal about OCR confidence/quality."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class OcrResult:
    """Result of transcribing a single page image."""
    text: str
    quality: OcrQuality = OcrQuality.UNKNOWN
    flags: list[str] = field(default_factory=list)
    # True when the provider reports low confidence or an error condition
    low_confidence: bool = False
    # Extra metadata the provider wants to surface (e.g. Tesseract PSI)
    metadata: dict = field(default_factory=dict)


class OcrProviderError(RuntimeError):
    """A provider failure that must not be treated as empty OCR text."""

    public_message = "The OCR service is busy. Please retry in a few minutes."


class OcrQuotaError(OcrProviderError):
    public_message = "The OCR service is at its usage limit. Please try again later."


class OcrBusyError(OcrProviderError):
    public_message = "The OCR service is busy. Please retry in a few minutes."


class OcrAuthError(OcrProviderError):
    public_message = "OCR service is not configured correctly."


def classify_ocr_provider_error(exc: BaseException | None) -> OcrProviderError:
    """Map a provider/SDK exception to a typed, user-safe OCR error."""
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__
    reason = " ".join(parts).lower()

    if any(
        marker in reason
        for marker in (
            "429",
            "resourceexhausted",
            "quota",
            "rate limit",
            "rate_limit",
            "too many requests",
            "billing",
        )
    ):
        return OcrQuotaError()
    if any(
        marker in reason
        for marker in (
            "api key",
            "api_key",
            "invalid key",
            "permission",
            "unauthorized",
            "unauthenticated",
            "401",
            "403",
        )
    ):
        return OcrAuthError()
    return OcrBusyError()


class OcrProvider(ABC):
    """Interface for OCR providers."""

    @abstractmethod
    async def transcribe_page(self, image_bytes: bytes, mime_type: str) -> OcrResult:
        """Transcribe a single page image.

        Args:
            image_bytes: Raw image bytes (JPEG/PNG/WebP).
            mime_type: MIME type of the image (e.g. "image/jpeg").

        Returns:
            OcrResult with extracted text and quality signals.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


def flag_needs_review(result: OcrResult, min_length: int = 50) -> bool:
    """Determine whether a page should be flagged for review.

    Flags when:
    - Output is very short (< min_length chars)
    - Contains many [illegible] markers
    - Provider signals low confidence
    """
    text = result.text
    if len(text) < min_length:
        return True
    if result.low_confidence:
        return True
    if "illegible" in text.lower():
        # Count occurrences — more than 5 is suspicious
        count = text.lower().count("[illegible]")
        if count > 5:
            return True
    return False
