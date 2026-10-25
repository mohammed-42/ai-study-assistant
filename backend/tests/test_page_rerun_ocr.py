"""Tests for POST /documents/{document_id}/pages/{page_id}/rerun-ocr."""

from __future__ import annotations

import math
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.ocr import OcrQuality, OcrResult
from app.api.deps import get_current_user
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.profile import Profile


@pytest.fixture
def client(db_session, test_user):
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    rate_limiter.reset()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        rate_limiter.reset()


async def _seed_page(
    db_session,
    test_user,
    test_subject,
    *,
    text: str = "Old page text that should remain until OCR succeeds.",
    image_key: str | None = "user/x/doc/0.png",
    source: str = "text_layer",
) -> tuple[Document, DocumentPage, list[DocumentChunk]]:
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Rerun.pdf",
        doc_type="image",
        status=DocumentStatus.READY,
        storage_key="user/x/doc/0.png",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    page = DocumentPage(
        document_id=doc.id,
        page_number=1,
        text=text,
        source=source,
        needs_review=False,
        user_edited=True,
        page_image_key=image_key,
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    chunk = DocumentChunk(
        document_id=doc.id,
        page_start=1,
        page_end=1,
        content=text,
        token_count=len(text) // 4,
        embedding=[0.2] * 768,
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)
    return doc, page, [chunk]


def _provider(new_text: str, *, ocr_error: Exception | None = None,
              embed_error: Exception | None = None) -> MagicMock:
    provider = MagicMock()

    async def transcribe(_image: bytes, _mime: str) -> OcrResult:
        if ocr_error is not None:
            raise ocr_error
        return OcrResult(text=new_text, quality=OcrQuality.HIGH)

    async def embed(texts: list[str]) -> list[list[float]]:
        if embed_error is not None:
            raise embed_error
        return [[0.4] * 768 for _ in texts]

    provider.transcribe_page = AsyncMock(side_effect=transcribe)
    provider.embed_texts = AsyncMock(side_effect=embed)
    return provider


def _mock_storage(monkeypatch, data: bytes = b"fake-png-bytes") -> None:
    storage = MagicMock()
    storage.storage.from_("documents").download.return_value = data
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: storage)


async def _chunks_for(db_session, doc_id) -> list[DocumentChunk]:
    db_session.expire_all()
    result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_rerun_ocr_replaces_text_and_chunks(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc, page, old_chunks = await _seed_page(db_session, test_user, test_subject)
    doc_id, page_id = doc.id, page.id
    old_ids = {chunk.id for chunk in old_chunks}
    new_text = "Fresh OCR text " * 120

    _mock_storage(monkeypatch)
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider", lambda: _provider(new_text)
    )

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == new_text
    assert body["source"] == "ocr"
    assert body["user_edited"] is False

    db_session.expire_all()
    refreshed = await db_session.get(DocumentPage, page_id)
    assert refreshed.text == new_text
    assert refreshed.source == "ocr"
    assert refreshed.user_edited is False

    chunks = await _chunks_for(db_session, doc_id)
    assert chunks
    assert old_ids.isdisjoint({chunk.id for chunk in chunks})
    assert all(
        any(abs(value) > 0.0 for value in chunk.embedding) for chunk in chunks
    )
    assert all(math.sqrt(sum(v * v for v in chunk.embedding)) > 0.0 for chunk in chunks)


@pytest.mark.asyncio
async def test_rerun_ocr_failure_keeps_old_text_and_chunks(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc, page, old_chunks = await _seed_page(db_session, test_user, test_subject)
    doc_id, page_id = doc.id, page.id
    old_text = page.text
    old_ids = {chunk.id for chunk in old_chunks}

    _mock_storage(monkeypatch)
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider",
        lambda: _provider("", ocr_error=RuntimeError("ocr down")),
    )

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 502
    assert "Could not re-read" in response.json()["detail"]

    db_session.expire_all()
    refreshed = await db_session.get(DocumentPage, page_id)
    assert refreshed.text == old_text
    assert refreshed.source == "text_layer"
    assert {chunk.id for chunk in await _chunks_for(db_session, doc_id)} == old_ids


@pytest.mark.asyncio
async def test_rerun_ocr_embedding_failure_keeps_old_text_and_chunks(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc, page, old_chunks = await _seed_page(db_session, test_user, test_subject)
    doc_id, page_id = doc.id, page.id
    old_text = page.text
    old_ids = {chunk.id for chunk in old_chunks}

    _mock_storage(monkeypatch)
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider",
        lambda: _provider("Fresh text", embed_error=RuntimeError("embed down")),
    )

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 502
    assert "Could not embed" in response.json()["detail"]

    db_session.expire_all()
    refreshed = await db_session.get(DocumentPage, page_id)
    assert refreshed.text == old_text
    assert {chunk.id for chunk in await _chunks_for(db_session, doc_id)} == old_ids


@pytest.mark.asyncio
async def test_rerun_ocr_other_user_gets_404(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc, page, _old_chunks = await _seed_page(db_session, test_user, test_subject)

    other_user = Profile(sub="other-rerun", email="other-rerun@example.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_mock = MagicMock()
    other_mock.id = other_user.id
    other_mock.email = other_user.email
    app.dependency_overrides[get_current_user] = lambda: other_mock

    _mock_storage(monkeypatch)
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider", lambda: _provider("Fresh text")
    )

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rerun_ocr_page_without_image_gets_400(
    db_session, test_user, test_subject, client, monkeypatch
):
    doc, page, _old_chunks = await _seed_page(
        db_session, test_user, test_subject, image_key=None
    )

    _mock_storage(monkeypatch)
    monkeypatch.setattr(
        "app.services.processing._get_ocr_provider", lambda: _provider("Fresh text")
    )

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 400
    assert response.json()["detail"] == "This page has no image to re-read."


@pytest.mark.asyncio
async def test_rerun_ocr_daily_limit_reached(
    db_session, test_user, test_subject, client, monkeypatch
):
    from app.core.config import settings

    doc, page, _old_chunks = await _seed_page(db_session, test_user, test_subject)
    today_page = DocumentPage(
        document_id=doc.id,
        page_number=2,
        text="Already OCRed today",
        source="ocr",
    )
    db_session.add(today_page)
    await db_session.commit()

    monkeypatch.setattr(settings, "OCR_LIMIT_PAGES_PER_USER_PER_DAY", 1)
    _mock_storage(monkeypatch)
    provider = _provider("Fresh text")
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: provider)

    response = client.post(f"/api/documents/{doc.id}/pages/{page.id}/rerun-ocr")

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Daily OCR limit reached. Try again tomorrow or upload fewer pages."
    )
    assert provider.transcribe_page.await_count == 0
