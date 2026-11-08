"""Tests for database-resolved tutor citations."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage, PageSource
from app.models.profile import Profile
from app.rag.citations import resolve_citations
from app.rag.generator import AnswerResult, generate_answer
from app.rag.retriever import RetrievalResult


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


async def _make_cited_document(db_session, owner_id, subject_id):
    document = Document(
        owner_id=owner_id,
        subject_id=subject_id,
        name="Biology Notes",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    pages = [
        DocumentPage(
            document_id=document.id,
            page_number=1,
            text="Cell theory",
            source=PageSource.TEXT_LAYER,
        ),
        DocumentPage(
            document_id=document.id,
            page_number=2,
            text="Mitochondria",
            source=PageSource.OCR,
            needs_review=True,
            user_edited=False,
        ),
        DocumentPage(
            document_id=document.id,
            page_number=3,
            text="Ribosomes",
            source=PageSource.OCR,
            needs_review=False,
            user_edited=True,
        ),
    ]
    db_session.add_all(pages)
    await db_session.commit()

    chunks = [
        DocumentChunk(
            document_id=document.id,
            page_start=1,
            page_end=2,
            content="Cell theory and mitochondria",
            token_count=6,
        ),
        DocumentChunk(
            document_id=document.id,
            page_start=2,
            page_end=2,
            content="Mitochondria",
            token_count=2,
        ),
        DocumentChunk(
            document_id=document.id,
            page_start=1,
            page_end=1,
            content="Cell theory",
            token_count=2,
        ),
    ]
    db_session.add_all(chunks)
    await db_session.commit()
    for chunk in chunks:
        await db_session.refresh(chunk)
    return document, pages, chunks


@pytest.mark.asyncio
async def test_resolve_citations_returns_name_pages_and_ocr_flags(
    db_session, test_user, test_subject
):
    _document, pages, chunks = await _make_cited_document(
        db_session, test_user.id, test_subject.id
    )

    resolved = await resolve_citations(
        db_session,
        test_user.id,
        [str(chunks[0].id), str(chunks[1].id), str(chunks[2].id)],
    )

    assert [citation.chunk_id for citation in resolved] == [str(chunk.id) for chunk in chunks]

    spanning = resolved[0]
    assert spanning.document_name == "Biology Notes"
    assert spanning.page_start == 1
    assert spanning.page_end == 2
    assert spanning.is_ocr is True
    assert spanning.needs_review is True
    assert spanning.user_edited is False
    assert spanning.has_unverified_ocr is True

    unedited_ocr = resolved[1]
    assert unedited_ocr.page_start == 2
    assert unedited_ocr.page_end == 2
    assert unedited_ocr.is_ocr is True
    assert unedited_ocr.has_unverified_ocr is True

    text_layer = resolved[2]
    assert text_layer.page_start == 1
    assert text_layer.page_end == 1
    assert text_layer.is_ocr is False
    assert text_layer.has_unverified_ocr is False

    pages[1].user_edited = True
    await db_session.commit()
    edited = await resolve_citations(db_session, test_user.id, [str(chunks[1].id)])
    assert edited[0].user_edited is True
    assert edited[0].has_unverified_ocr is False


@pytest.mark.asyncio
async def test_resolve_citations_drops_invalid_and_foreign_chunks(
    db_session, test_user, test_subject
):
    _document, _pages, chunks = await _make_cited_document(
        db_session, test_user.id, test_subject.id
    )

    other_user = Profile(sub="other-citation-user", email="other-cite@example.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_document = Document(
        owner_id=other_user.id,
        subject_id=test_subject.id,
        name="Other Notes",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(other_document)
    await db_session.commit()
    await db_session.refresh(other_document)

    other_chunk = DocumentChunk(
        document_id=other_document.id,
        page_start=1,
        page_end=1,
        content="Private content",
        token_count=2,
    )
    db_session.add(other_chunk)
    await db_session.commit()
    await db_session.refresh(other_chunk)

    resolved = await resolve_citations(
        db_session,
        test_user.id,
        [str(chunks[2].id), str(other_chunk.id), "not-a-uuid", str(uuid.uuid4())],
    )

    assert [citation.chunk_id for citation in resolved] == [str(chunks[2].id)]


@pytest.mark.asyncio
async def test_generate_answer_drops_citation_not_in_retrieved_set():
    valid_id = uuid.uuid4()
    chunk = RetrievalResult(
        chunk_id=valid_id,
        document_id=uuid.uuid4(),
        page_start=1,
        page_end=1,
        content="Cells contain mitochondria.",
        similarity=0.9,
        document_name="Biology Notes",
    )
    response = MagicMock()
    response.text = json.dumps({
        "answer": "Cells contain mitochondria.",
        "citations": [str(valid_id), str(uuid.uuid4())],
        "evidence_sufficient": True,
    })

    with patch("app.rag.generator.create_client"), patch(
        "app.ai.gemini.call_with_retry",
        new=AsyncMock(return_value=response),
    ):
        result = await generate_answer("What do cells contain?", [chunk])

    assert result.citations == [str(valid_id)]


@pytest.mark.asyncio
async def test_post_message_returns_resolved_citations(
    db_session, test_user, test_subject, client
):
    _document, _pages, chunks = await _make_cited_document(
        db_session, test_user.id, test_subject.id
    )
    session_resp = client.post("/api/chat/sessions", json={"title": "Citations"})
    session_id = session_resp.json()["id"]

    answer = AnswerResult(
        answer="Cells contain mitochondria.",
        citations=[str(chunks[0].id), str(uuid.uuid4())],
        is_insufficient=False,
    )
    with patch(
        "app.api.chat._generate_ai_response",
        new=AsyncMock(return_value=answer),
    ):
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What do cells contain?"},
        )

    assert response.status_code == 201
    data = response.json()
    assert len(data["citations"]) == 1
    citation = data["citations"][0]
    assert citation["chunk_id"] == str(chunks[0].id)
    assert citation["document_id"] == str(_document.id)
    assert citation["document_name"] == "Biology Notes"
    assert citation["page_start"] == 1
    assert citation["page_end"] == 2
    assert citation["is_ocr"] is True
    assert citation["has_unverified_ocr"] is True

    messages = client.get(f"/api/chat/sessions/{session_id}/messages").json()
    assistant = messages[-1]
    assert assistant["citations"][0]["chunk_id"] == str(chunks[0].id)
    assert assistant["citations"][0]["document_name"] == "Biology Notes"
