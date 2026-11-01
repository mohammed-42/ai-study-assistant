"""Tests for documents API."""

import io
import uuid
from datetime import datetime, timezone
from uuid import UUID
import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.subject import Subject
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage, PageSource
from app.models.document_chunk import DocumentChunk
from app.models.processing_job import ProcessingJob, JobStatus


@pytest.fixture
def client(db_session, test_user):
    """Create test client with auth overridden."""
    mock_user = MagicMock()
    mock_user.id = test_user.id
    mock_user.email = test_user.email

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_documents_empty(db_session, test_user, test_subject, client):
    """Test listing documents when none exist."""
    response = client.get("/api/documents/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_create_document(db_session, test_user, test_subject, client):
    """Test creating a document via upload."""
    response = client.post(
        "/api/documents/upload",
        files={"files": ("Test.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test.pdf"
    assert data["status"] == "uploaded"
    assert data["subject_id"] == str(test_subject.id)


@pytest.mark.asyncio
async def test_get_document(db_session, test_user, test_subject, client):
    """Test getting a single document."""
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("Math Notes.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    response = client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Math Notes.pdf"


@pytest.mark.asyncio
async def test_list_documents_by_subject(db_session, test_user, test_subject, client):
    """Test filtering documents by subject."""
    # Create two documents for same subject
    client.post(
        "/api/documents/upload",
        files={"files": ("Doc1.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    client.post(
        "/api/documents/upload",
        files={"files": ("Doc2.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )

    response = client.get(f"/api/documents/?subject_id={test_subject.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_documents_paginated(db_session, test_user, test_subject, client):
    """Test limit/offset pagination while preserving the unpaginated default."""
    for index in range(3):
        db_session.add(
            Document(
                owner_id=test_user.id,
                subject_id=test_subject.id,
                name=f"Doc {index}.pdf",
                doc_type="pdf",
                status=DocumentStatus.UPLOADED,
                created_at=datetime(2024, 1, index + 1, tzinfo=timezone.utc),
            )
        )
    await db_session.commit()

    response = client.get("/api/documents/", params={"limit": 2, "offset": 1})
    assert response.status_code == 200
    assert [doc["name"] for doc in response.json()] == ["Doc 1.pdf", "Doc 0.pdf"]

    response = client.get("/api/documents/")
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_list_documents_filtered_pagination(db_session, test_user, test_subject, client):
    """Subject filtering happens before limit/offset so pages stay correct."""
    other_subject = Subject(owner_id=test_user.id, name="Physics")
    db_session.add(other_subject)
    await db_session.commit()
    await db_session.refresh(other_subject)

    for index in range(3):
        db_session.add(
            Document(
                owner_id=test_user.id,
                subject_id=test_subject.id,
                name=f"Math {index}.pdf",
                doc_type="pdf",
                status=DocumentStatus.UPLOADED,
                created_at=datetime(2024, 2, index + 1, tzinfo=timezone.utc),
            )
        )
    for index in range(2):
        db_session.add(
            Document(
                owner_id=test_user.id,
                subject_id=other_subject.id,
                name=f"Physics {index}.pdf",
                doc_type="pdf",
                status=DocumentStatus.UPLOADED,
                created_at=datetime(2024, 3, index + 1, tzinfo=timezone.utc),
            )
        )
    await db_session.commit()

    response = client.get(
        "/api/documents/",
        params={"subject_id": str(test_subject.id), "limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    assert [doc["name"] for doc in response.json()] == ["Math 1.pdf", "Math 0.pdf"]


@pytest.mark.asyncio
async def test_delete_document(db_session, test_user, test_subject, client):
    """Test deleting a document."""
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("ToDelete.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    response = client.delete(f"/api/documents/{doc_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_document_ownership_isolation(db_session, test_user, test_subject, client):
    """Test that users can only access their own documents."""
    # Create document
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("MyDoc.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    # Create another user
    other_user = Profile(sub="other-sub-002", email="other@example.com", full_name="Other User")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    # Simulate other user trying to access
    other_mock = MagicMock()
    other_mock.id = other_user.id
    other_mock.email = other_user.email

    app.dependency_overrides[get_current_user] = lambda: other_mock
    try:
        response = client.get(f"/api/documents/{doc_id}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthenticated_request():
    """Test that unauthenticated requests are rejected."""
    client = TestClient(app)
    response = client.get("/api/documents/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_document_pages(db_session, test_user, test_subject, client):
    """Test listing pages for a document."""
    # Create document
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("Test.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    # Add pages
    for i in range(3):
        page = DocumentPage(
            document_id=UUID(doc_id),
            page_number=i + 1,
            text=f"Content of page {i+1}",
            source=PageSource.TEXT_LAYER,
        )
        db_session.add(page)
    await db_session.commit()

    response = client.get(f"/api/documents/{doc_id}/pages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["page_number"] == 1
    assert data[0]["text"] == "Content of page 1"


@pytest.mark.asyncio
async def test_list_document_chunks(db_session, test_user, test_subject, client):
    """Test listing chunks for a document."""
    # Create document
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("Test.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    # Add chunks
    for i in range(2):
        chunk = DocumentChunk(
            document_id=UUID(doc_id),
            page_start=i + 1,
            page_end=i + 1,
            content=f"Chunk {i+1} content",
            token_count=50,
        )
        db_session.add(chunk)
    await db_session.commit()

    response = client.get(f"/api/documents/{doc_id}/chunks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["content"] == "Chunk 1 content"


@pytest.mark.asyncio
async def test_retry_failed_document(db_session, test_user, test_subject, client):
    """Test retrying a failed document."""
    # Create and fail document
    create_resp = client.post(
        "/api/documents/upload",
        files={"files": ("Failed.pdf", io.BytesIO(b"%PDF-1.4 test"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    doc_id = create_resp.json()["id"]

    # Mark as failed
    doc = await db_session.get(Document, UUID(doc_id))
    doc.status = DocumentStatus.FAILED
    doc.error_message = "Processing error"
    await db_session.commit()

    # Retry
    response = client.post(f"/api/documents/{doc_id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "uploaded"
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_chunking_logic():
    """Test the chunking function."""
    from app.services.processing import chunk_text

    text = "A" * 1000  # 1000 characters
    chunks = chunk_text(text, chunk_size=100, overlap=20)

    # Should create multiple chunks
    assert len(chunks) >= 2
    # Each chunk should be approximately correct size
    for chunk in chunks:
        assert len(chunk) <= 400  # 100 tokens * 4 chars/token


@pytest.mark.asyncio
async def test_processing_pipeline_stub():
    """Test that processing pipeline exists and has expected structure."""
    from app.services.processing import process_document, chunk_text

    # Just verify imports work
    assert callable(process_document)
    assert callable(chunk_text)


@pytest.mark.asyncio
async def test_upload_invalid_pdf(db_session, test_user, test_subject, client):
    """Test uploading an invalid PDF."""
    response = client.post(
        "/api/documents/upload",
        files={"files": ("fake.pdf", io.BytesIO(b"not a real pdf"))},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_process_document_with_session(db_session, test_user, test_subject):
    """Direct process_document call uses the passed-in session."""
    from app.services.processing import process_document

    # Create a document directly in the test session
    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="Direct.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED)
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # No storage mock -> 0 pages -> failed
    with pytest.raises(RuntimeError):
        await process_document(db_session, str(doc.id))

    # Re-query via the same session to confirm status changed
    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.page_count == 0
    assert refreshed.error_message == "No readable text was found in this file."


@pytest.mark.asyncio
async def test_process_document_background_with_session(db_session, test_user, test_subject):
    """Background wrapper uses provided session when passed explicitly."""
    from app.services.processing import process_document_background

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="BgTask.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED)
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    # Pass the test session explicitly — this is how it works with in-memory SQLite
    await process_document_background(doc_id, db=db_session)

    refreshed = await db_session.get(Document, uuid.UUID(doc_id))
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.page_count == 0
    assert refreshed.error_message == "No readable text was found in this file."


@pytest.mark.asyncio
async def test_process_document_background_auto_session(monkeypatch):
    """Background wrapper creates its own session when none is provided."""
    from app.services.processing import process_document_background

    mock_db = MagicMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_maker = MagicMock(return_value=mock_db)

    processed_with = []

    async def fake_process_document(db, document_id):
        processed_with.append((db, document_id))

    monkeypatch.setattr("app.services.processing.process_document", fake_process_document)
    monkeypatch.setattr("app.db.base.get_session_maker", lambda: mock_maker)

    await process_document_background("doc-123")

    mock_maker.assert_called_once()
    assert len(processed_with) == 1
    assert processed_with[0][0] is mock_db
    assert processed_with[0][1] == "doc-123"


@pytest.mark.asyncio
async def test_process_document_background_handles_missing_doc(db_session):
    """Background wrapper handles missing document gracefully — no exception."""
    from app.services.processing import process_document_background

    fake_id = str(uuid.uuid4())
    # Should not raise
    await process_document_background(fake_id)


@pytest.mark.asyncio
async def test_process_pdf_creates_chunks_and_embeddings(db_session, test_user, test_subject, monkeypatch):
    """PDF processing creates pages, chunks, and embeddings from real PDF text."""
    import fitz, tempfile, os
    from app.services.processing import process_document
    from app.models.document_chunk import DocumentChunk

    # Create a real multi-page PDF
    tmpdir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmpdir, "chunkable.pdf")
    pdf_doc = fitz.open()
    for i in range(3):
        page = pdf_doc.new_page()
        page.insert_text((72, 72 + i * 120), f"Page {i+1} content about React fundamentals and hooks.")
    pdf_doc.save(pdf_path)
    pdf_doc.close()
    pdf_bytes = open(pdf_path, "rb").read()
    os.unlink(pdf_path)
    os.rmdir(tmpdir)

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="ChunkTest.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="test.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    # Mock storage download to return our PDF bytes
    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    async def fake_embed(texts):
        return [[0.1] * 768 for _ in texts]

    mock_provider = MagicMock()
    mock_provider.embed_texts = AsyncMock(side_effect=fake_embed)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.READY
    assert refreshed.page_count == 3

    # Verify pages exist
    pages = await db_session.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number))
    page_list = list(pages.scalars().all())
    assert len(page_list) == 3
    assert all(p.text.strip() for p in page_list)

    # Verify chunks exist
    chunks = await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    chunk_list = list(chunks.scalars().all())
    assert len(chunk_list) >= 1
    assert all(c.content.strip() for c in chunk_list)

    # Every persisted chunk must have a real (non-zero) embedding.
    assert all(any(abs(value) > 0.0 for value in c.embedding) for c in chunk_list)


@pytest.mark.asyncio
async def test_process_image_creates_chunks_and_embeddings(db_session, test_user, test_subject, monkeypatch):
    """Image processing creates pages, chunks, and embeddings from OCR."""
    from app.services.processing import process_document
    from app.models.document_chunk import DocumentChunk

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="ImgTest.jpg", doc_type="image", status=DocumentStatus.UPLOADED)
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)
    folder = f"user/{test_user.id}/{doc_id}"
    doc.storage_key = f"{folder}/0_img.jpg"
    await db_session.commit()

    # Mock storage to return a valid PNG image (1x1 pixel)
    import io
    from PIL import Image
    img = Image.new("RGB", (10, 10), color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    png_data = img_bytes.read()

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").list.return_value = [{"name": "0_img.jpg"}]
    mock_storage.storage.from_("documents").download.return_value = png_data
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    # Mock OCR provider to return deterministic text
    from app.ai.ocr import OcrResult, OcrQuality
    mock_provider = MagicMock()
    mock_provider.transcribe_page = AsyncMock(return_value=OcrResult(text="Test OCR text content for chunking.", quality=OcrQuality.HIGH, flags=[], low_confidence=False))
    mock_provider.embed_texts = AsyncMock(return_value=[[0.1] * 768])
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.READY
    assert refreshed.page_count == 1

    pages = await db_session.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id))
    page_list = list(pages.scalars().all())
    assert len(page_list) == 1
    assert page_list[0].page_image_key == f"{folder}/0_img.jpg"

    storage_api = mock_storage.storage.from_.return_value
    storage_api.list.assert_called_once_with(folder)
    storage_api.download.assert_called_once_with(f"{folder}/0_img.jpg")

    chunks = await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    chunk_list = list(chunks.scalars().all())
    assert len(chunk_list) >= 1


@pytest.mark.asyncio
async def test_process_document_no_pages_fails(db_session, test_user, test_subject):
    """Document with 0 extractable pages fails with a user-readable message."""
    from app.services.processing import process_document

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="Empty.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="missing.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    # No storage mock — _process_pdf will fail to download and return early
    with pytest.raises(RuntimeError):
        await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.page_count == 0
    assert refreshed.error_message == "No readable text was found in this file."

    chunks = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    assert list(chunks.scalars().all()) == []


@pytest.mark.asyncio
async def test_process_document_embedding_failure_fails_without_chunks(
    db_session, test_user, test_subject, monkeypatch
):
    """Embedding failure marks failed and persists no chunks."""
    from app.services.processing import process_document
    import fitz, tempfile, os

    tmpdir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmpdir, "embed-fail.pdf")
    pdf_doc = fitz.open()
    pdf_doc.new_page().insert_text((72, 72), "Embedding failure test content.")
    pdf_doc.save(pdf_path)
    pdf_doc.close()
    pdf_bytes = open(pdf_path, "rb").read()
    os.unlink(pdf_path)
    os.rmdir(tmpdir)

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="EmbedFail.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="embed-fail.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    mock_provider = MagicMock()
    mock_provider.embed_texts = AsyncMock(side_effect=RuntimeError("network error"))
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == "Embedding service unavailable. Please retry."

    chunks = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    assert list(chunks.scalars().all()) == []


@pytest.mark.asyncio
async def test_process_document_all_empty_ocr_pages_fails(
    db_session, test_user, test_subject, monkeypatch
):
    """A document whose OCR pages are all empty fails with the no-text message."""
    from app.services.processing import process_document
    from app.ai.ocr import OcrResult, OcrQuality
    import io
    from PIL import Image

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="EmptyOCR.jpg", doc_type="image", status=DocumentStatus.UPLOADED)
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)
    folder = f"user/{test_user.id}/{doc_id}"
    doc.storage_key = f"{folder}/0_a.png"
    await db_session.commit()

    img = Image.new("RGB", (10, 10), color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    png_data = img_bytes.read()

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").list.return_value = [
        {"name": "0_a.png"},
        {"name": "1_b.png"},
    ]
    mock_storage.storage.from_("documents").download.return_value = png_data
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    mock_provider = MagicMock()
    mock_provider.transcribe_page = AsyncMock(
        return_value=OcrResult(
            text="",
            quality=OcrQuality.LOW,
            flags=["no_text_detected"],
            low_confidence=True,
        )
    )
    mock_provider.embed_texts = AsyncMock(return_value=[[0.1] * 768])
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == "No readable text was found in this file."

    chunks = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    assert list(chunks.scalars().all()) == []


@pytest.mark.asyncio
async def test_process_document_missing_gemini_key_fails(
    db_session, test_user, test_subject, monkeypatch
):
    """Missing Gemini configuration fails clearly instead of persisting zero vectors."""
    from app.services.processing import process_document
    from app.core.config import settings
    import fitz, tempfile, os

    tmpdir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmpdir, "no-key.pdf")
    pdf_doc = fitz.open()
    pdf_doc.new_page().insert_text((72, 72), "Text that needs an embedding.")
    pdf_doc.save(pdf_path)
    pdf_doc.close()
    pdf_bytes = open(pdf_path, "rb").read()
    os.unlink(pdf_path)
    os.rmdir(tmpdir)

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="NoKey.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="no-key.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OCR_FALLBACK_ENABLED", False)

    with pytest.raises(RuntimeError):
        await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.FAILED
    assert refreshed.error_message == "AI service is not configured. Please retry after configuration."

    chunks = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    assert list(chunks.scalars().all()) == []


@pytest.mark.asyncio
async def test_retry_after_embedding_failure_succeeds_without_duplicate_chunks(
    db_session, test_user, test_subject, client, monkeypatch
):
    """Retry resets a failed document and succeeds without duplicate chunks."""
    from app.services.processing import process_document
    import fitz, tempfile, os

    tmpdir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmpdir, "retry-embed.pdf")
    pdf_doc = fitz.open()
    pdf_doc.new_page().insert_text((72, 72), "Retry after embedding failure.")
    pdf_doc.save(pdf_path)
    pdf_doc.close()
    pdf_bytes = open(pdf_path, "rb").read()
    os.unlink(pdf_path)
    os.rmdir(tmpdir)

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="RetryEmbed.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="retry-embed.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    calls = {"count": 0}

    async def flaky_embed(texts):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary embedding outage")
        return [[0.2] * 768 for _ in texts]

    mock_provider = MagicMock()
    mock_provider.embed_texts = AsyncMock(side_effect=flaky_embed)
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    with pytest.raises(RuntimeError):
        await process_document(db_session, doc_id)

    failed = await db_session.get(Document, doc.id)
    assert failed.status == DocumentStatus.FAILED

    retry_response = client.post(f"/api/documents/{doc_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "uploaded"

    await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.READY
    assert refreshed.page_count == 1
    assert refreshed.error_message is None

    chunks = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    chunk_list = list(chunks.scalars().all())
    assert len(chunk_list) >= 1
    assert all(any(abs(value) > 0.0 for value in c.embedding) for c in chunk_list)
    assert len(chunk_list) == len({c.content for c in chunk_list})


@pytest.mark.asyncio
async def test_process_document_retry_clears_old_data(db_session, test_user, test_subject, monkeypatch):
    """Retrying a document clears old pages/chunks before reprocessing."""
    from app.services.processing import process_document
    from app.models.document_chunk import DocumentChunk
    import fitz, tempfile, os

    doc = Document(owner_id=test_user.id, subject_id=test_subject.id, name="Retry.pdf", doc_type="pdf", status=DocumentStatus.UPLOADED, storage_key="retry.pdf")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    doc_id = str(doc.id)

    # First pass: create some stale pages/chunks
    from app.models.document_page import DocumentPage as DP
    stale_page = DP(document_id=doc.id, page_number=1, text="stale text", source="text_layer")
    db_session.add(stale_page)
    await db_session.commit()

    # Create a real PDF for second pass
    tmpdir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmpdir, "retry.pdf")
    pdf_doc = fitz.open()
    pdf_doc.new_page().insert_text((72, 72), "Fresh content after retry.")
    pdf_doc.save(pdf_path)
    pdf_doc.close()
    pdf_bytes = open(pdf_path, "rb").read()
    os.unlink(pdf_path)
    os.rmdir(tmpdir)

    mock_storage = MagicMock()
    mock_storage.storage.from_("documents").download.return_value = pdf_bytes
    monkeypatch.setattr("app.services.processing._get_storage_client", lambda: mock_storage)

    mock_provider = MagicMock()
    mock_provider.embed_texts = AsyncMock(return_value=[[0.3] * 768])
    monkeypatch.setattr("app.services.processing._get_ocr_provider", lambda: mock_provider)

    # Second pass (retry)
    await process_document(db_session, doc_id)

    refreshed = await db_session.get(Document, doc.id)
    assert refreshed.status == DocumentStatus.READY

    # Old stale page should be gone
    pages = await db_session.execute(select(DP).where(DP.document_id == doc.id))
    page_list = list(pages.scalars().all())
    assert len(page_list) == 1
    assert page_list[0].text == "Fresh content after retry."


@pytest.mark.asyncio
async def test_upload_file_too_large(db_session, test_user, test_subject, client):
    """Test uploading a file that's too large."""
    # Create a file larger than 50MB
    large_file = io.BytesIO(b"x" * (51 * 1024 * 1024))
    response = client.post(
        "/api/documents/upload",
        files={"files": ("big.pdf", large_file)},
        params={"subject_id": str(test_subject.id), "doc_type": "pdf"}
    )
    assert response.status_code == 413
