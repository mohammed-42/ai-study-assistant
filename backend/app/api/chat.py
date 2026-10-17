"""Chat-related endpoints for the tutor feature."""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.profile import Profile
from app.rag.generator import AnswerResult, generate_answer
from app.rag.retriever import RetrievalResult, retrieve_chunks
from app.schemas.chat import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    MessageCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


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


@router.get("/sessions/{session_id}/messages", response_model=list[dict])
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List all messages in a chat session."""
    await _get_owner_session(db, uuid.UUID(session_id), user.id)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # Convert to dicts with parsed citation_ids
    output = []
    for msg in messages:
        citation_ids = None
        if msg.citation_ids:
            try:
                citation_ids = json.loads(msg.citation_ids)
            except (json.JSONDecodeError, TypeError):
                citation_ids = []
        output.append({
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "role": msg.role,
            "content": msg.content,
            "citation_ids": citation_ids,
            "is_insufficient": msg.is_insufficient,
            "created_at": msg.created_at.isoformat(),
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
        
        # Parse citation IDs from JSON string if needed
        citation_ids = answer.citations
        if isinstance(citation_ids, str):
            try:
                citation_ids = [str(x) for x in json.loads(citation_ids)]
            except Exception:
                citation_ids = []
        
        # Save assistant message
        # citation_ids stored as JSON string in DB
        citation_ids_list = answer.citations if isinstance(answer.citations, list) else []
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
        
        # Return as dict with parsed citation_ids
        return {
            "id": str(assistant_msg.id),
            "session_id": str(assistant_msg.session_id),
            "role": assistant_msg.role,
            "content": assistant_msg.content,
            "citation_ids": citation_ids_list,
            "is_insufficient": assistant_msg.is_insufficient,
            "created_at": assistant_msg.created_at.isoformat(),
        }
        
    except Exception as exc:
        logger.error("AI response generation failed: %s", exc)
        # Save error message
        error_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content="抱歉，服务暂时不可用，请稍后重试。",
            is_insufficient=True,
        )
        db.add(error_msg)
        await db.commit()
        await db.refresh(error_msg)
        return error_msg


@router.post("/sessions/{session_id}/messages/stream", status_code=200)
async def stream_message(
    session_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Stream a user message and get a streaming AI response."""
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
    
    async def generate_stream() -> AsyncGenerator[str, None]:
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
                stream=True,
            )
            yield answer
        except Exception as exc:
            logger.error("Streaming failed: %s", exc)
            yield "Error: " + str(exc)
    
    return generate_stream()


async def _generate_ai_response(
    db: AsyncSession,
    question: str,
    session_id: uuid.UUID,
    owner_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    min_similarity: float = 0.6,
    stream: bool = False,
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
