"""Page-level endpoints — edit OCR text and re-embed."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.profile import Profile
from app.schemas.document import DocumentPageOut
from app.services.processing import re_embed_page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/{document_id}/pages", tags=["pages"])


class PageEditRequest(BaseModel):
    """Request body for editing a page's OCR text."""
    text: str = Field(..., min_length=0, max_length=50000)
    needs_review: bool | None = None
    user_edited: bool = True


@router.put("/{page_id}", response_model=DocumentPageOut)
async def edit_page(
    document_id: str,
    page_id: str,
    body: PageEditRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
) -> DocumentPage:
    """Edit OCR text for a page and trigger re-embedding."""
    doc_stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.owner_id == user.id,
    )
    doc_result = await db.execute(doc_stmt)
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    page_stmt = select(DocumentPage).where(DocumentPage.id == uuid.UUID(page_id))
    page_result = await db.execute(page_stmt)
    page = page_result.scalar_one_or_none()
    if page is None or page.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")

    page.text = body.text
    if body.needs_review is not None:
        page.needs_review = body.needs_review
    page.user_edited = body.user_edited
    await db.commit()
    await db.refresh(page)

    # Re-chunk and re-embed in background
    try:
        import asyncio
        asyncio.create_task(re_embed_page(db, page.id, body.text))  # noqa: RUF006 — fire-and-forget
    except Exception as exc:
        logger.warning("Re-embed task failed: %s", exc)

    return page
