"""Processing pipeline for document ingestion."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr import OcrProvider, OcrResult, flag_needs_review
from app.ai.tesseract import TesseractOcrProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy import of fitz (PyMuPDF) to avoid DLL issues in test env
_fitz: object | None = None


def _get_fitz():
    global _fitz
    if _fitz is None:
        try:
            import fitz  # noqa: PLC0415
            _fitz = fitz
        except ImportError as exc:
            raise ImportError(f"PyMuPDF (fitz) not available: {exc}") from exc
    return _fitz


async def process_document(db: AsyncSession, document_id: str) -> None:
    """Process a document: extract text, create pages, chunk, embed."""
    doc = await _get_document(db, uuid.UUID(document_id))
    if doc is None:
        return

    doc.status = "processing"
    await db.commit()

    try:
        if doc.doc_type == "pdf":
            await _process_pdf(db, doc)
        elif doc.doc_type in ("image", "multi_image"):
            await _process_images(db, doc)
        else:
            raise ValueError(f"unknown doc_type: {doc.doc_type}")

        doc.status = "ready"
        doc.page_count = await _count_pages(db, doc.id)

    except Exception as exc:
        doc.status = "failed"
        doc.error_message = str(exc)[:2000]
        logger.exception("Document %s processing failed", document_id)
        raise
    finally:
        await db.commit()


async def _get_document(db: AsyncSession, doc_id: uuid.UUID):
    stmt = select(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _process_pdf(db: AsyncSession, doc: Document) -> None:
    """Extract text from PDF — uses text layer when available, OCR fallback."""
    fitz = _get_fitz()
    # TODO: Load PDF bytes from storage key
    # For now this is a placeholder — real implementation needs storage access
    page_count = 0  # Will be set from actual pages after processing

    for page_num in range(page_count):
        # TODO: Render page at ~200 DPI for OCR if no text layer
        page_text = ""
        source = "text_layer"
        needs_review = False

        page = DocumentPage(
            document_id=doc.id,
            page_number=page_num + 1,
            text=page_text,
            source=source,
            needs_review=needs_review,
        )
        db.add(page)

    await db.commit()


async def _process_images(
    db: AsyncSession,
    doc: Document,
    ocr_provider: OcrProvider | None = None,
) -> None:
    """Process uploaded images — runs OCR on each image page."""
    # TODO: Load image bytes from storage keys
    # Placeholder: iterate over doc's pages (already stored as image references)
    image_pages = await _get_image_pages(db, doc.id)

    if not image_pages:
        logger.warning("No image pages found for document %s", doc.id)
        return

    provider = ocr_provider or _get_ocr_provider()
    if provider is None:
        raise RuntimeError("No OCR provider configured and GEMINI_API_KEY is not set")

    # Check daily limit
    await _check_daily_ocr_limit(db, doc.owner_id, len(image_pages))

    for idx, (page_info, image_bytes, mime_type) in enumerate(image_pages):
        result = await provider.transcribe_page(image_bytes, mime_type)
        needs_review = flag_needs_review(result)

        page = DocumentPage(
            document_id=doc.id,
            page_number=idx + 1,
            text=result.text,
            source="ocr",
            needs_review=needs_review,
            page_image_key=page_info.get("storage_key"),
        )
        db.add(page)

        # Small delay between requests to respect rate limits
        await asyncio.sleep(0.1)

    await db.commit()


async def _check_daily_ocr_limit(db: AsyncSession, owner_id: uuid.UUID, pages_to_process: int) -> None:
    """Raise if the user has hit their daily OCR page limit."""
    limit = settings.OCR_LIMIT_PAGES_PER_USER_PER_DAY
    if not limit:
        return

    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(DocumentPage)
        .where(
            DocumentPage.document_id.in_(
                select(Document.id).where(Document.owner_id == owner_id)
            ),
            DocumentPage.source == "ocr",
            DocumentPage.created_at >= start_of_day,
        )
    )
    result = await db.execute(stmt)
    already_today = len(result.scalars().all())

    if already_today + pages_to_process > limit:
        raise RuntimeError(
            f"Daily OCR limit reached ({limit} pages). "
            f"Already processed {already_today} today, attempting {pages_to_process} more."
        )


def _get_ocr_provider() -> OcrProvider | None:
    """Return the configured OCR provider, or None if not configured."""
    api_key = settings.GEMINI_API_KEY
    if api_key and api_key != "your-gemini-api-key":
        try:
            from app.ai.gemini import GeminiOcrProvider
            return GeminiOcrProvider()
        except Exception as exc:
            logger.warning("Failed to init Gemini provider: %s", exc)

    if settings.OCR_FALLBACK_ENABLED:
        try:
            return TesseractOcrProvider()
        except Exception as exc:
            logger.warning("Failed to init Tesseract provider: %s", exc)

    return None


async def _get_image_pages(
    db: AsyncSession, doc_id: uuid.UUID
) -> list[tuple[dict, bytes, str]]:
    """Load image bytes and metadata for each page of an image/multi_image document.

    Returns list of (page_info_dict, image_bytes, mime_type).
    TODO: Replace with actual storage reads once Supabase Storage is wired.
    """
    # Placeholder — returns empty list; real impl reads from storage_key
    return []


async def _count_pages(db: AsyncSession, doc_id: uuid.UUID) -> int:
    stmt = select(DocumentPage).where(DocumentPage.document_id == doc_id)
    result = await db.execute(stmt)
    return len(result.scalars().all())


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into token-aware chunks (approximate using chars)."""
    chars_per_token = 4
    chunk_chars = chunk_size * chars_per_token
    overlap_chars = overlap * chars_per_token

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap_chars

    return chunks


async def create_chunks(db: AsyncSession, document_id: uuid.UUID, pages: list[DocumentPage]) -> None:
    """Create document chunks from pages."""
    all_text = "\n\n".join(p.text for p in pages)
    chunks = chunk_text(all_text)

    for i, chunk_content in enumerate(chunks):
        total_pages = len(pages)
        chunk_size = len(all_text) / max(len(chunks), 1)
        page_start = int(i * chunk_size / max(len(pages), 1))
        page_end = min(total_pages, page_start + 1)

        chunk = DocumentChunk(
            document_id=document_id,
            page_start=page_start + 1,
            page_end=page_end + 1,
            content=chunk_content,
            token_count=len(chunk_content) // 4,
        )
        db.add(chunk)

    await db.commit()


async def embed_chunks(
    db: AsyncSession,
    chunks: list[DocumentChunk],
    ocr_provider: OcrProvider | None = None,
) -> None:
    """Generate embeddings for chunks using the configured provider."""
    provider = ocr_provider or _get_ocr_provider()
    if provider is None:
        logger.warning("No OCR provider available — skipping embedding generation")
        return

    texts = [c.content for c in chunks if c.content.strip()]
    if not texts:
        return

    vectors = await provider.embed_texts(texts)

    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector

    await db.commit()


async def re_embed_page(db: AsyncSession, page_id: uuid.UUID, new_text: str) -> None:
    """Re-chunk and re-embed a single page after user edit.

    Removes old chunks for this page, creates new ones, and re-embeds.
    """
    from app.models.document_chunk import DocumentChunk as ChunkModel

    # Find the document this page belongs to
    page_stmt = select(DocumentPage).where(DocumentPage.id == page_id)
    page_result = await db.execute(page_stmt)
    page = page_result.scalar_one_or_none()
    if page is None:
        raise ValueError(f"Page {page_id} not found")

    doc_id = page.document_id

    # Delete old chunks for this page
    delete_stmt = select(DocumentChunk).where(
        DocumentChunk.document_id == doc_id,
        DocumentChunk.page_start <= page.page_number,
        DocumentChunk.page_end >= page.page_number,
    )
    old_chunks = (await db.execute(delete_stmt)).scalars().all()
    for chunk in old_chunks:
        await db.delete(chunk)
    await db.commit()

    # Re-chunk with updated text
    # Rebuild all page texts
    all_pages_stmt = (
        select(DocumentPage)
        .where(DocumentPage.document_id == doc_id)
        .order_by(DocumentPage.page_number)
    )
    all_pages = (await db.execute(all_pages_stmt)).scalars().all()
    # Replace this page's text
    for p in all_pages:
        if p.id == page_id:
            p.text = new_text
    await db.commit()

    await create_chunks(db, doc_id, list(all_pages))

    # Re-embed
    chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
    all_chunks = (await db.execute(chunk_stmt)).scalars().all()
    await embed_chunks(db, list(all_chunks))


# Imports needed at runtime (avoid circular)
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.document_chunk import DocumentChunk  # noqa: E402
