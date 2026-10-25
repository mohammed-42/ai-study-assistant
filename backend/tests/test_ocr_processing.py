"""Processing tests for scanned-PDF rendering and OCR page selection."""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import fitz
import pytest
from PIL import Image
from sqlalchemy import select

from app.ai.ocr import OcrQuality, OcrResult
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.services.processing import OCR_RENDER_DPI, process_document


def _page_image_bytes(width: int = 600, height: int = 800) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_pdf(page_kinds: list[str]) -> tuple[bytes, float]:
    """Build a PDF whose pages are either text-layer pages or image-only pages."""
    pdf = fitz.open()
    image_bytes = _page_image_bytes()
    for kind in page_kinds:
        page = pdf.new_page(width=595, height=842)
        if kind == "text":
            page.insert_text((72, 72), "This page already has a real text layer.")
        else:
            page.insert_image(page.rect, stream=image_bytes)
    data = pdf.tobytes()
    width = pdf[0].rect.width
    pdf.close()
    return data, width


def _mock_provider(captured_images: list[bytes]) -> MagicMock:
    provider = MagicMock()

    async def transcribe(image: bytes, _mime: str) -> OcrResult:
        captured_images.append(image)
        return OcrResult(
            text="Scanned page text returned by the mocked OCR provider for testing.",
            quality=OcrQuality.HIGH,
        )

    async def embed(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    provider.transcribe_page = AsyncMock(side_effect=transcribe)
    provider.embed_texts = AsyncMock(side_effect=embed)
    return provider


async def _create_pdf_document(db_session, test_user, test_subject, pdf_bytes: bytes) -> Document:
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Scanned.pdf",
        doc_type="pdf",
        status=DocumentStatus.UPLOADED,
        storage_key="scanned.pdf",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_scanned_pdf_renders_at_200_dpi(
    db_session, test_user, test_subject, monkeypatch
):
    from app.services.processing import OCR_RENDER_DPI as render_dpi

    assert render_dpi == 200

    pdf_bytes, page_width = _build_pdf(["image"])
    doc = await _create_pdf_document(db_session, test_user, test_subject, pdf_bytes)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    captured: list[bytes] = []
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider",
        lambda: _mock_provider(captured),
    )

    await process_document(db_session, str(doc.id))

    assert len(captured) == 1
    rendered = Image.open(io.BytesIO(captured[0]))
    expected_width = page_width * (render_dpi / 72)
    assert abs(rendered.width - expected_width) / expected_width <= 0.02

    pages = (
        await db_session.execute(
            select(DocumentPage).where(DocumentPage.document_id == doc.id)
        )
    ).scalars().all()
    assert [p.source for p in pages] == ["ocr"]


@pytest.mark.asyncio
async def test_mixed_pdf_uses_text_layer_then_ocr(
    db_session, test_user, test_subject, monkeypatch
):
    pdf_bytes, _ = _build_pdf(["text", "image"])
    doc = await _create_pdf_document(db_session, test_user, test_subject, pdf_bytes)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    captured: list[bytes] = []
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider",
        lambda: _mock_provider(captured),
    )

    await process_document(db_session, str(doc.id))

    pages = (
        await db_session.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.page_number)
        )
    ).scalars().all()
    assert [p.source for p in pages] == ["text_layer", "ocr"]
    assert len(captured) == 1
    assert pages[1].text.startswith("Scanned page text")


@pytest.mark.asyncio
async def test_over_per_document_ocr_cap_fails_without_calling_ocr(
    db_session, test_user, test_subject, monkeypatch
):
    from app.core.config import settings

    pdf_bytes, _ = _build_pdf(["image", "image", "image"])
    doc = await _create_pdf_document(db_session, test_user, test_subject, pdf_bytes)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_DOC", 2)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 100)

    captured: list[bytes] = []
    provider = _mock_provider(captured)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, str(doc.id))

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == (
        "This file needs OCR on 3 pages, which is over the limit of 2 pages per file."
    )
    assert provider.transcribe_page.await_count == 0
    assert captured == []


@pytest.mark.asyncio
async def test_scanned_pdf_over_daily_limit_fails_without_calling_ocr(
    db_session, test_user, test_subject, monkeypatch
):
    from app.core.config import settings

    pdf_bytes, _ = _build_pdf(["image", "image"])
    doc = await _create_pdf_document(db_session, test_user, test_subject, pdf_bytes)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_DOC", 50)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 1)

    captured: list[bytes] = []
    provider = _mock_provider(captured)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, str(doc.id))

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == (
        "Daily OCR limit reached. Try again tomorrow or upload fewer pages."
    )
    assert provider.transcribe_page.await_count == 0
    assert captured == []


@pytest.mark.asyncio
async def test_ocr_exactly_at_per_document_cap_passes(
    db_session, test_user, test_subject, monkeypatch
):
    from app.core.config import settings

    pdf_bytes, _ = _build_pdf(["image", "image"])
    doc = await _create_pdf_document(db_session, test_user, test_subject, pdf_bytes)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_DOC", 2)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 100)

    captured: list[bytes] = []
    provider = _mock_provider(captured)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    await process_document(db_session, str(doc.id))

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.READY
    assert provider.transcribe_page.await_count == 2
    assert len(captured) == 2
