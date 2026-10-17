"""Tests for chat/tutor API endpoints."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.api.deps import get_current_user
from app.models.profile import Profile
from app.models.subject import Subject
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage


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


# --- Session CRUD tests ---


@pytest.mark.asyncio
async def test_list_sessions_empty(db_session, test_user, client):
    """Test listing sessions when none exist."""
    response = client.get("/api/chat/sessions")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_session(db_session, test_user, client, test_subject):
    """Test creating a chat session."""
    response = client.post("/api/chat/sessions", json={
        "subject_id": str(test_subject.id),
        "title": "Math Discussion"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Math Discussion"
    assert data["subject_id"] == str(test_subject.id)


@pytest.mark.asyncio
async def test_create_session_no_subject(db_session, test_user, client):
    """Test creating a session without subject."""
    response = client.post("/api/chat/sessions", json={"title": "General Chat"})
    assert response.status_code == 201
    data = response.json()
    assert data["subject_id"] is None


@pytest.mark.asyncio
async def test_delete_session(db_session, test_user, client):
    """Test deleting a session."""
    # Create session
    create_resp = client.post("/api/chat/sessions", json={"title": "Test Session"})
    session_id = create_resp.json()["id"]

    # Delete
    response = client.delete(f"/api/chat/sessions/{session_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_session_ownership_isolation(db_session, test_user, client):
    """Test that users can only access their own sessions."""
    # Create session for test user
    create_resp = client.post("/api/chat/sessions", json={"title": "My Session"})
    session_id = create_resp.json()["id"]

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
        response = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# --- Message tests ---


@pytest.mark.asyncio
async def test_list_messages_empty(db_session, test_user, client):
    """Test listing messages when none exist."""
    create_resp = client.post("/api/chat/sessions", json={"title": "Empty Chat"})
    session_id = create_resp.json()["id"]

    response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_post_message_requires_auth():
    """Test that posting messages requires authentication."""
    client = TestClient(app)
    response = client.post("/api/chat/sessions/test-session/messages", json={
        "content": "Hello"
    })
    assert response.status_code == 401


# --- Retrieval authorization tests ---


@pytest.mark.asyncio
async def test_retrieve_chunks_ownership_filter(db_session, test_user, test_subject):
    """Test that retrieval only returns chunks from user's own documents."""
    from app.rag.retriever import retrieve_chunks
    
    # Create user's document with chunks
    user_doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="User's Document",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(user_doc)
    await db_session.commit()
    await db_session.refresh(user_doc)

    chunk = DocumentChunk(
        document_id=user_doc.id,
        page_start=1,
        page_end=1,
        content="This is relevant content about quantum mechanics.",
        token_count=10,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk)
    await db_session.commit()

    # Create another user's document
    other_user = Profile(sub="other-sub-002", email="other@example.com")
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    other_doc = Document(
        owner_id=other_user.id,
        subject_id=test_subject.id,
        name="Other's Document",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(other_doc)
    await db_session.commit()
    await db_session.refresh(other_doc)

    other_chunk = DocumentChunk(
        document_id=other_doc.id,
        page_start=1,
        page_end=1,
        content="This is other user's content.",
        token_count=10,
        embedding=[0.2] * 768,
    )
    db_session.add(other_chunk)
    await db_session.commit()

    # Retrieve for test_user
    results = await retrieve_chunks(
        db=db_session,
        query_embedding=[0.1] * 768,
        owner_id=test_user.id,
        top_k=5,
    )

    # Should only return user's chunks
    assert len(results) == 1
    assert results[0].document_name == "User's Document"
    assert results[0].owner_id == test_user.id


# --- Citation validation tests ---


@pytest.mark.asyncio
async def test_citation_validation():
    """Test that invalid citations are filtered out."""
    from app.rag.generator import AnswerResult

    # Simulate answer with mixed valid/invalid citations
    result = AnswerResult(
        answer="Test answer",
        citations=["valid-chunk-1", "invalid-chunk-2", "valid-chunk-3"],
        is_insufficient=False,
    )

    available_ids = {"valid-chunk-1", "valid-chunk-3"}
    validated = [c for c in result.citations if c in available_ids]
    assert validated == ["valid-chunk-1", "valid-chunk-3"]


@pytest.mark.asyncio
async def test_insufficient_evidence_path():
    """Test insufficient evidence response."""
    from app.rag.generator import AnswerResult

    result = AnswerResult(
        answer="",
        citations=[],
        is_insufficient=True,
    )

    assert result.is_insufficient is True
    assert result.answer == ""


# --- End-to-end answer generation test ---


@pytest.mark.asyncio
async def test_answer_generation_with_retrieval(db_session, test_user, test_subject, client):
    """Test the full answer generation flow with mocked Gemini."""
    from app.rag.retriever import RetrievalResult

    # Create document with chunks
    doc = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Physics Notes",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    chunk1 = DocumentChunk(
        document_id=doc.id,
        page_start=1,
        page_end=1,
        content="Newton's first law states that an object at rest stays at rest.",
        token_count=15,
        embedding=[0.8] * 768,
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        page_start=2,
        page_end=2,
        content="Friction is a force that opposes motion between surfaces.",
        token_count=12,
        embedding=[0.3] * 768,
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.commit()

    # Create session
    session_resp = client.post("/api/chat/sessions", json={
        "subject_id": str(test_subject.id),
        "title": "Physics Q&A"
    })
    session_id = session_resp.json()["id"]

    # Mock the Gemini embedding and generation
    mock_answer = {
        "answer": "According to your notes, Newton's first law states that an object at rest stays at rest unless acted upon by an external force.",
        "citations": [str(chunk1.id)],
        "evidence_sufficient": True,
    }

    with patch('app.rag.generator.genai') as mock_genai, \
         patch('app.rag.retriever.retrieve_chunks') as mock_retrieve, \
         patch('app.ai.gemini.GeminiOcrProvider') as mock_provider_cls:
        
        # Setup mock provider
        mock_provider = MagicMock()
        mock_provider.embed_texts = AsyncMock(return_value=[[0.75] * 768])
        mock_provider_cls.return_value = mock_provider
        
        # Setup mock retriever
        mock_retrieve.return_value = [
            RetrievalResult(
                chunk_id=chunk1.id,
                document_id=doc.id,
                page_start=1,
                page_end=1,
                content=chunk1.content,
                similarity=0.85,
                document_name="Physics Notes",
            ),
        ]
        
        # Setup mock generator
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_answer)
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Post message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={
                "content": "What does Newton's first law say?",
                "subject_id": str(test_subject.id),
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "assistant"
        assert "Newton" in data["content"]
        assert data["is_insufficient"] is False

        # Verify messages were saved
        msg_resp = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert msg_resp.status_code == 200
        messages = msg_resp.json()
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_unauthenticated_chat_request(client):
    """Test that unauthenticated requests to chat are rejected."""
    from app.main import app as main_app
    # Remove the auth override
    if get_current_user in main_app.dependency_overrides:
        del main_app.dependency_overrides[get_current_user]

    response = client.get("/api/chat/sessions")
    assert response.status_code == 401
