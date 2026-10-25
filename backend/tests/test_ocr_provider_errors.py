"""OCR/embedding provider failures must surface clear, retryable errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.ocr import OcrBusyError, OcrQuality, OcrQuotaError, OcrResult
from app.api.deps import get_current_user
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.processing_job import ProcessingJob
from app.services.processing import process_document


@pytest.fixture
def client(db_session, test_user):
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


async def _create_image_doc(db_session, test_user, test_subject, name: str) -> Document:
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name=name,
        doc_type="image",
        status=DocumentStatus.UPLOADED,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc.storage_key = f"user/{test_user.id}/{doc.id}/0_img.png"
    await db_session.commit()
    return doc


def _mock_storage(monkeypatch) -> None:
    storage = MagicMock()
    storage.storage.from_("documents").list.return_value = [{"name": "0_img.png"}]
    storage.storage.from_("documents").download.return_value = b"fake-image-bytes"
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: storage)


def _success_provider(text: str = "OCR text that is long enough to avoid a review flag.") -> MagicMock:
    provider = MagicMock()
    provider.transcribe_page = AsyncMock(
        return_value=OcrResult(text=text, quality=OcrQuality.HIGH)
    )
    provider.embed_texts = AsyncMock(
        side_effect=lambda texts: [[0.3] * 768 for _ in texts]
    )
    return provider


async def _counts(db_session, doc_id):
    pages = (
        await db_session.execute(
            select(DocumentPage).where(DocumentPage.document_id == doc_id)
        )
    ).scalars().all()
    chunks = (
        await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
    ).scalars().all()
    jobs = (
        await db_session.execute(
            select(ProcessingJob).where(ProcessingJob.document_id == doc_id)
        )
    ).scalars().all()
    return len(pages), len(chunks), jobs


@pytest.mark.asyncio
async def test_quota_error_fails_clearly_and_retry_succeeds(
    db_session, test_user, test_subject, client, monkeypatch
):
    from app.core.config import settings

    doc = await _create_image_doc(db_session, test_user, test_subject, "Quota.png")
    doc_id = doc.id
    _mock_storage(monkeypatch)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_DOC", 50)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 100)

    calls = {"count": 0}

    async def transcribe(_image: bytes, _mime: str) -> OcrResult:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OcrQuotaError()
        return OcrResult(text="OCR text recovered on retry, long enough for review.", quality=OcrQuality.HIGH)

    provider = _success_provider()
    provider.transcribe_page = AsyncMock(side_effect=transcribe)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    with pytest.raises(OcrQuotaError):
        await process_document(db_session, str(doc_id))

    db_session.expire_all()
    refreshed = await db_session.get(Document, doc_id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == (
        "The OCR service is at its usage limit. Please try again later."
    )
    pages_count, chunks_count, jobs = await _counts(db_session, doc_id)
    assert pages_count == 0
    assert chunks_count == 0
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert all(job.status != "running" for job in jobs)

    response = client.post(f"/api/documents/{doc_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"

    await process_document(db_session, str(doc_id))

    db_session.expire_all()
    refreshed = await db_session.get(Document, doc_id)
    assert refreshed.status == DocumentStatus.READY
    assert refreshed.error_message is None
    pages_count, chunks_count, jobs = await _counts(db_session, doc_id)
    assert pages_count == 1
    assert chunks_count >= 1
    assert all(job.status != "running" for job in jobs)


@pytest.mark.asyncio
async def test_timeout_maps_to_busy_message(
    db_session, test_user, test_subject, monkeypatch
):
    doc = await _create_image_doc(db_session, test_user, test_subject, "Busy.png")
    doc_id = doc.id
    _mock_storage(monkeypatch)

    provider = _success_provider()
    provider.transcribe_page = AsyncMock(side_effect=OcrBusyError())
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    with pytest.raises(OcrBusyError):
        await process_document(db_session, str(doc_id))

    db_session.expire_all()
    refreshed = await db_session.get(Document, doc_id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == (
        "The OCR service is busy. Please retry in a few minutes."
    )


@pytest.mark.asyncio
async def test_empty_ocr_text_is_no_readable_text(
    db_session, test_user, test_subject, monkeypatch
):
    doc = await _create_image_doc(db_session, test_user, test_subject, "Empty.png")
    doc_id = doc.id
    _mock_storage(monkeypatch)

    provider = _success_provider()
    provider.transcribe_page = AsyncMock(
        return_value=OcrResult(
            text="",
            quality=OcrQuality.LOW,
            flags=["no_text_detected"],
            low_confidence=True,
        )
    )
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, str(doc_id))

    db_session.expire_all()
    refreshed = await db_session.get(Document, doc_id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == "No readable text was found in this file."


@pytest.mark.asyncio
async def test_failed_ocr_pages_do_not_count_toward_daily_limit(
    db_session, test_user, test_subject, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_DOC", 50)
    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 1)
    _mock_storage(monkeypatch)

    first = await _create_image_doc(db_session, test_user, test_subject, "First.png")
    first_id = first.id
    failing = _success_provider()
    failing.transcribe_page = AsyncMock(side_effect=OcrQuotaError())
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: failing)

    with pytest.raises(OcrQuotaError):
        await process_document(db_session, str(first_id))

    db_session.expire_all()
    failed_pages = (
        await db_session.execute(
            select(DocumentPage).where(
                DocumentPage.document_id == first_id,
                DocumentPage.source == "ocr",
            )
        )
    ).scalars().all()
    assert failed_pages == []

    await db_session.refresh(test_user)
    await db_session.refresh(test_subject)
    second = await _create_image_doc(db_session, test_user, test_subject, "Second.png")
    second_id = second.id
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider", lambda: _success_provider()
    )

    await process_document(db_session, str(second_id))

    db_session.expire_all()
    refreshed = await db_session.get(Document, second_id)
    assert refreshed.status == DocumentStatus.READY
    assert refreshed.error_message is None
