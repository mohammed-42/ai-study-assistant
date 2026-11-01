"""Resolve cited chunk IDs into database-backed citation details."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage, PageSource


@dataclass
class ResolvedCitation:
    """Citation details resolved from the database."""

    chunk_id: str
    document_id: str
    document_name: str
    page_start: int
    page_end: int
    is_ocr: bool
    needs_review: bool
    user_edited: bool
    has_unverified_ocr: bool


def _is_ocr_page(page: DocumentPage) -> bool:
    return page.source == PageSource.OCR or page.source == "ocr"


def _ordered_unique_ids(chunk_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for chunk_id in chunk_ids:
        value = str(chunk_id)
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


async def resolve_citations(
    db: AsyncSession,
    owner_id: uuid.UUID,
    chunk_ids: list[str],
) -> list[ResolvedCitation]:
    """Resolve chunk IDs for one owner, dropping missing or foreign chunks."""
    ordered_ids = _ordered_unique_ids(chunk_ids)
    if not ordered_ids:
        return []

    valid_ids: list[uuid.UUID] = []
    for chunk_id in ordered_ids:
        try:
            valid_ids.append(uuid.UUID(chunk_id))
        except (ValueError, AttributeError, TypeError):
            continue
    if not valid_ids:
        return []

    chunk_stmt = (
        select(DocumentChunk, Document.name)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.id.in_(valid_ids),
            Document.owner_id == owner_id,
        )
    )
    chunk_rows = (await db.execute(chunk_stmt)).all()
    chunks_by_id = {str(chunk.id): (chunk, document_name) for chunk, document_name in chunk_rows}
    if not chunks_by_id:
        return []

    doc_ids = {chunk.document_id for chunk, _name in chunks_by_id.values()}
    page_stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id.in_(doc_ids))
        .order_by(DocumentPage.page_number)
    )
    pages = (await db.execute(page_stmt)).scalars().all()

    pages_by_doc: dict[uuid.UUID, list[DocumentPage]] = {}
    for page in pages:
        pages_by_doc.setdefault(page.document_id, []).append(page)

    resolved: list[ResolvedCitation] = []
    for chunk_id in ordered_ids:
        row = chunks_by_id.get(chunk_id)
        if row is None:
            continue
        chunk, document_name = row
        source_pages = [
            page
            for page in pages_by_doc.get(chunk.document_id, [])
            if chunk.page_start <= page.page_number <= chunk.page_end
        ]
        is_ocr = any(_is_ocr_page(page) for page in source_pages)
        resolved.append(
            ResolvedCitation(
                chunk_id=chunk_id,
                document_id=str(chunk.document_id),
                document_name=document_name,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                is_ocr=is_ocr,
                needs_review=any(page.needs_review for page in source_pages),
                user_edited=any(page.user_edited for page in source_pages),
                has_unverified_ocr=any(
                    _is_ocr_page(page) and not page.user_edited
                    for page in source_pages
                ),
            )
        )

    return resolved
