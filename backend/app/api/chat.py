"""Chat-related endpoints for the tutor feature."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr import OcrQuotaError, classify_ocr_provider_error
from app.api.deps import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.db.base import get_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.document import Document
from app.models.profile import Profile
from app.rag.citations import resolve_citations
from app.rag.generator import AnswerResult, generate_answer
from app.rag.retriever import retrieve_chunks
from app.schemas.chat import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    CitationOut,
    MessageCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _parse_citation_ids(raw: str | None) -> list[str]:
    """Parse stored citation IDs, tolerating legacy values."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    citation_ids: list[str] = []
    for item in data:
        value = item.get("chunk_id") if isinstance(item, dict) else item
        if value:
            citation_ids.append(str(value))
    return citation_ids


# --- Session endpoints ---


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List all chat sessions owned by the current user."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.owner_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(
    body: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Create a new chat session."""
    # Verify subject ownership if provided
    if body.subject_id:
        from app.models.subject import Subject
        subject_stmt = select(Subject).where(
            Subject.id == body.subject_id,
            Subject.owner_id == user.id,
        )
        subject_result = await db.execute(subject_stmt)
        if subject_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="subject not found or not owned",
            )

    session = ChatSession(
        owner_id=user.id,
        subject_id=body.subject_id,
        title=body.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    session = await _get_owner_session(db, uuid.UUID(session_id), user.id)
    await db.delete(session)
    await db.commit()
    return None


# --- Message endpoints ---


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List all messages in a chat session with resolved citations."""
    await _get_owner_session(db, uuid.UUID(session_id), user.id)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    parsed_ids = {
        msg.id: _parse_citation_ids(msg.citation_ids)
        for msg in messages
    }
    all_citation_ids = [
        citation_id
        for citation_ids in parsed_ids.values()
        for citation_id in citation_ids
    ]
    resolved = await resolve_citations(db, user.id, all_citation_ids)
    citations_by_chunk = {citation.chunk_id: citation for citation in resolved}

    output = []
    for msg in messages:
        citations = [
            CitationOut.model_validate(citations_by_chunk[citation_id])
            for citation_id in parsed_ids[msg.id]
            if citation_id in citations_by_chunk
        ]
        output.append({
            "id": msg.id,
            "session_id": msg.session_id,
            "role": msg.role,
            "content": msg.content,
            "citations": citations,
            "is_insufficient": msg.is_insufficient,
            "created_at": msg.created_at,
        })
    return output


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageOut, status_code=201)
async def post_message(
    session_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Post a user message and get an AI-generated response with citations."""
    await enforce_rate_limit("ai", user.id, "RATE_LIMIT_AI_PER_MINUTE")
    session = await _get_owner_session(db, uuid.UUID(session_id), user.id)
    
    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    
    # Generate AI response
    try:
        answer = await _generate_ai_response(
            db=db,
            question=body.content,
            session_id=session.id,
            owner_id=user.id,
            subject_id=body.subject_id,
            document_ids=body.document_ids,
            top_k=body.top_k,
            min_similarity=body.min_similarity,
        )
        
        # Resolve citations from the database, dropping invalid/foreign IDs.
        raw_citations = answer.citations
        if isinstance(raw_citations, str):
            citation_ids_list = _parse_citation_ids(raw_citations)
        else:
            citation_ids_list = [str(citation_id) for citation_id in raw_citations]
        citations = await resolve_citations(db, user.id, citation_ids_list)

        # Save assistant message
        # citation_ids stored as JSON string in DB
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer.answer,
            citation_ids=json.dumps(citation_ids_list) if citation_ids_list else None,
            is_insufficient=answer.is_insufficient,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Return as dict with resolved citations
        return {
            "id": assistant_msg.id,
            "session_id": assistant_msg.session_id,
            "role": assistant_msg.role,
            "content": assistant_msg.content,
            "citations": [CitationOut.model_validate(citation) for citation in citations],
            "is_insufficient": assistant_msg.is_insufficient,
            "created_at": assistant_msg.created_at,
        }
        
    except Exception as exc:
        logger.error("AI response generation failed: %s", exc)
        if isinstance(classify_ocr_provider_error(exc), OcrQuotaError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The AI service is at its usage limit. Please try again later.",
            ) from exc
        # Save error message
        error_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content="The tutor is temporarily unavailable. Please try again.",
            is_insufficient=True,
        )
        db.add(error_msg)
        await db.commit()
        await db.refresh(error_msg)
        return {
            "id": error_msg.id,
            "session_id": error_msg.session_id,
            "role": error_msg.role,
            "content": error_msg.content,
            "citations": [],
            "is_insufficient": error_msg.is_insufficient,
            "created_at": error_msg.created_at,
        }


async def _generate_ai_response(
    db: AsyncSession,
    question: str,
    session_id: uuid.UUID,
    owner_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    min_similarity: float = 0.5,
) -> AnswerResult:
    """Generate AI response with RAG retrieval."""
    from app.ai.gemini import GeminiOcrProvider
    
    # Get conversation history
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(20)
    )
    history_result = await db.execute(history_stmt)
    history_messages = history_result.scalars().all()
    
    conversation_history = []
    for msg in history_messages:
        conversation_history.append({
            "role": msg.role,
            "content": msg.content,
        })
    
    # Remove the current question from history (it's already saved)
    conversation_history = conversation_history[:-1] if conversation_history else []
    
    # Retrieve relevant chunks
    # First, get embedding for the query
    provider = GeminiOcrProvider()
    query_embedding = await provider.embed_texts([question])
    query_vec = query_embedding[0] if query_embedding else [0.0] * 768
    
    # Get allowed document IDs for this user
    doc_stmt = select(Document.id).where(Document.owner_id == owner_id)
    if subject_id:
        doc_stmt = doc_stmt.where(Document.subject_id == subject_id)
    user_docs_result = await db.execute(doc_stmt)
    user_docs = user_docs_result.scalars().all()
    
    # Filter document_ids to only those owned by user
    if document_ids:
        document_ids = [did for did in document_ids if did in user_docs]
    
    retrieved = await retrieve_chunks(
        db=db,
        query_embedding=query_vec,
        owner_id=owner_id,
        subject_id=subject_id,
        document_ids=document_ids,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    
    # Generate answer
    return await generate_answer(
        question=question,
        retrieved_chunks=retrieved,
        conversation_history=conversation_history,
    )


async def _get_owner_session(db: AsyncSession, session_id: uuid.UUID, owner_id: uuid.UUID) -> ChatSession:
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.owner_id == owner_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found or not owned",
        )
    return session
