"""Notes API endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.note import Note
from app.models.profile import Profile
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.note import NoteCreate, NoteOut, NoteUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
async def list_notes(
    subject_id: uuid.UUID | None = Query(None),
    document_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """List notes owned by current user, optionally filtered by subject or document."""
    stmt = select(Note).where(Note.owner_id == user.id)
    if subject_id:
        # Verify subject ownership
        from app.models.subject import Subject
        subj = await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")
        stmt = stmt.where(Note.subject_id == subject_id)
    if document_id:
        doc = await db.execute(
            select(Document).where(Document.id == document_id, Document.owner_id == user.id)
        )
        if doc.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found or not owned")
        stmt = stmt.where(Note.document_id == document_id)
    stmt = stmt.order_by(Note.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Create a new note."""
    if body.subject_id:
        from app.models.subject import Subject
        subj = await db.execute(
            select(Subject).where(Subject.id == body.subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")
    if body.document_id:
        doc = await db.execute(
            select(Document).where(Document.id == body.document_id, Document.owner_id == user.id)
        )
        if doc.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found or not owned")

    note = Note(
        owner_id=user.id,
        subject_id=body.subject_id,
        document_id=body.document_id,
        title=body.title,
        note_type=body.note_type,
        content=body.content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Get a note by ID."""
    note = await _get_owner_note(db, uuid.UUID(note_id), user.id)
    return note


@router.put("/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: str,
    body: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Update a note."""
    note = await _get_owner_note(db, uuid.UUID(note_id), user.id)
    if body.title is not None:
        note.title = body.title
    if body.note_type is not None:
        note.note_type = body.note_type
    if body.content is not None:
        note.content = body.content
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Delete a note."""
    note = await _get_owner_note(db, uuid.UUID(note_id), user.id)
    await db.delete(note)
    await db.commit()
    return None


@router.post("/generate", response_model=NoteOut, status_code=201)
async def generate_note(
    subject_id: uuid.UUID | None = Query(None),
    document_id: uuid.UUID | None = Query(None),
    note_type: str = Query("summary", pattern="^(summary|key_concepts|definitions|revision)$"),
    title: str = Query("Generated Note", max_length=500),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Generate notes from document chunks using Gemini."""
    from app.services.notes import generate_notes

    # Resolve document and collect chunks
    doc_chunks: list[DocumentChunk] = []
    if document_id:
        doc = await db.execute(
            select(Document).where(Document.id == document_id, Document.owner_id == user.id)
        )
        doc_obj = doc.scalar_one_or_none()
        if doc_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found or not owned")
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.page_start)
        )
        doc_chunks = chunks_result.scalars().all()
    elif subject_id:
        # Collect chunks from all documents in the subject
        from app.models.subject import Subject
        subj = await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.owner_id == user.id)
        )
        if subj.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")
        docs_result = await db.execute(
            select(Document).where(Document.subject_id == subject_id, Document.owner_id == user.id)
        )
        docs = docs_result.scalars().all()
        for doc in docs:
            chunks_result = await db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.page_start)
            )
            doc_chunks.extend(chunks_result.scalars().all())
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either document_id or subject_id must be provided",
        )

    if not doc_chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chunks found for the selected document(s)",
        )

    try:
        content = await generate_notes(doc_chunks, note_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    note = Note(
        owner_id=user.id,
        subject_id=subject_id,
        document_id=document_id,
        title=title,
        note_type=note_type,
        content=content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def _get_owner_note(db: AsyncSession, note_id: uuid.UUID, owner_id: uuid.UUID) -> Note:
    stmt = select(Note).where(Note.id == note_id, Note.owner_id == owner_id)
    result = await db.execute(stmt)
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="note not found or not owned")
    return note
