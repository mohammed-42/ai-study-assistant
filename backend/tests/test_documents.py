"""Tests for documents API."""

import io
import uuid
from uuid import UUID
import pytest
from unittest.mock import MagicMock
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
