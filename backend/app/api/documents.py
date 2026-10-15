from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.document_chunk import DocumentChunk
from app.models.processing_job import ProcessingJob
from app.models.profile import Profile
from app.schemas.document import DocumentOut, DocumentPageOut, DocumentChunkOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    subject_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    stmt = select(Document).where(Document.owner_id == user.id)
    if subject_id:
        stmt = stmt.where(Document.subject_id == subject_id)
    stmt = stmt.order_by(desc(Document.created_at))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    # Verify subject ownership
    from app.models.subject import Subject
    subject_stmt = select(Subject).where(
        Subject.id == body.subject_id,
        Subject.owner_id == user.id,
    )
    subject_result = await db.execute(subject_stmt)
    if subject_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found or not owned")

    doc = Document(
        owner_id=user.id,
        subject_id=body.subject_id,
        name=body.name,
        doc_type=body.doc_type,
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    doc = await _get_owner_document(db, UUID(document_id), user.id)
    return doc


@router.get("/{document_id}/pages", response_model=list[DocumentPageOut])
async def list_document_pages(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await _get_owner_document(db, UUID(document_id), user.id)
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id == UUID(document_id))
        .order_by(DocumentPage.page_number)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkOut])
async def list_document_chunks(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    await _get_owner_document(db, UUID(document_id), user.id)
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == UUID(document_id))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{document_id}/retry", response_model=DocumentOut)
async def retry_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    doc = await _get_owner_document(db, UUID(document_id), user.id)
    if doc.status != DocumentStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only failed documents can be retried")
    doc.status = DocumentStatus.UPLOADED
    doc.error_message = None
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    doc = await _get_owner_document(db, UUID(document_id), user.id)
    # Delete in order: chunks → pages → storage key (storage handled separately)
    from sqlalchemy import delete
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
    await db.delete(doc)
    await db.commit()
    return None


async def _get_owner_document(db: AsyncSession, document_id: UUID, owner_id: UUID) -> Document:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.owner_id == owner_id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return doc
