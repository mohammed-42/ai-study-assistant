"""Page-level endpoints — edit OCR text and re-embed."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr import OcrProviderError
from app.api.deps import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.db.base import get_db
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.profile import Profile
from app.schemas.document import DocumentPageOut
from app.services.processing import (
    DocumentProcessingError,
    _check_daily_ocr_limit,
    re_embed_page_background,
    rerun_page_ocr,
)
from app.services.storage import create_signed_url

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
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> DocumentPage:
    """Edit OCR text for a page and trigger re-embedding."""
    await enforce_rate_limit("ai", user.id, "RATE_LIMIT_AI_PER_MINUTE")

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

    background_tasks.add_task(re_embed_page_background, page.id, body.text)

    return page


@router.post("/{page_id}/rerun-ocr", response_model=DocumentPageOut)
async def rerun_page_with_ocr(
    document_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
) -> DocumentPage:
    """Re-read a stored page image with OCR and atomically replace its text/chunks."""
    await enforce_rate_limit("ai", user.id, "RATE_LIMIT_AI_PER_MINUTE")

    doc_stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.owner_id == user.id,
    )
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    page = await db.get(DocumentPage, uuid.UUID(page_id))
    if page is None or page.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    if not page.page_image_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This page has no image to re-read.",
        )

    try:
        await _check_daily_ocr_limit(db, user.id, 1)
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    try:
        return await rerun_page_ocr(db, page)
    except OcrProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.public_message,
        ) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Re-run OCR failed for page %s: %s", page.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not re-read this page. Please try again.",
        ) from exc


@router.get("/{page_id}/image-url")
async def get_page_image_url(
    document_id: str,
    page_id: str,
    expires_in: int = Query(3600, ge=60, le=3600),
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(get_current_user),
):
    """Return a short-lived signed URL for a private page image."""
    doc_stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.owner_id == user.id,
    )
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    page = await db.get(DocumentPage, uuid.UUID(page_id))
    if page is None or page.document_id != doc.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")
    if not page.page_image_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page image not found")
    if not page.page_image_key.startswith(f"user/{user.id}/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="page image is not owned by user",
        )

    try:
        url = create_signed_url(page.page_image_key, expires_in)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.warning("Signed URL generation failed for page %s: %s", page.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not create a signed image URL",
        ) from exc

    return {"url": url, "expires_in": expires_in}
