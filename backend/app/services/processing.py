"""Processing pipeline for document ingestion."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ocr import OcrProvider, OcrProviderError, OcrResult, flag_needs_review
from app.ai.tesseract import TesseractOcrProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

OCR_RENDER_DPI = 200

NO_READABLE_TEXT_MESSAGE = "No readable text was found in this file."
EMBEDDING_UNAVAILABLE_MESSAGE = "Embedding service unavailable. Please retry."
AI_NOT_CONFIGURED_MESSAGE = "AI service is not configured. Please retry after configuration."
GENERIC_PROCESSING_ERROR_MESSAGE = "Processing failed. Please retry."
DAILY_OCR_LIMIT_MESSAGE = "Daily OCR limit reached. Try again tomorrow or upload fewer pages."
OCR_QUOTA_MESSAGE = "The OCR service is at its usage limit. Please try again later."
OCR_BUSY_MESSAGE = "The OCR service is busy. Please retry in a few minutes."
OCR_AUTH_MESSAGE = "OCR service is not configured correctly."
OCR_RERUN_FAILED_MESSAGE = "Could not re-read this page. Please try again."
OCR_RERUN_EMBED_FAILED_MESSAGE = "Could not embed the re-read page. Please try again."


class DocumentProcessingError(RuntimeError):
    """A processing failure whose message is safe to show to the user."""


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, DocumentProcessingError):
        return str(exc)
    if isinstance(exc, OcrProviderError):
        return exc.public_message
    return GENERIC_PROCESSING_ERROR_MESSAGE


def _has_real_embedding(vector: list[float] | None) -> bool:
    if not vector:
        return False
    return any(abs(float(value)) > 0.0 for value in vector)


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
    """Process a document: extract text, create pages, chunk, embed.

    Uses the passed-in database session. Callers are responsible for opening
    and closing the session (e.g. tests that supply their own fixture session).
    """
    doc = await _get_document(db, uuid.UUID(document_id))
    if doc is None:
        return

    doc.status = "processing"
    doc.error_message = None
    await db.commit()

    job = None
    job_finished = False
    try:
        job = await _start_processing_job(db, doc.id)

        # Clear old pages/chunks for idempotent retries
        await _clear_existing_pages_and_chunks(db, doc.id)

        if doc.doc_type == "pdf":
            await _process_pdf(db, doc)
        elif doc.doc_type in ("image", "multi_image"):
            await _process_images(db, doc)
        else:
            raise DocumentProcessingError(GENERIC_PROCESSING_ERROR_MESSAGE)

        # Create chunks from all pages, then embed them
        pages_stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == doc.id)
            .order_by(DocumentPage.page_number)
        )
        pages_result = await db.execute(pages_stmt)
        pages = list(pages_result.scalars().all())

        if not pages or not any(page.text and page.text.strip() for page in pages):
            raise DocumentProcessingError(NO_READABLE_TEXT_MESSAGE)

        await create_chunks(db, doc.id, pages)
        # Fetch newly created chunks for embedding
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        chunk_result = await db.execute(chunk_stmt)
        chunks = list(chunk_result.scalars().all())
        if not chunks:
            raise DocumentProcessingError(GENERIC_PROCESSING_ERROR_MESSAGE)

        await embed_chunks(db, chunks)

        if not pages or not any(page.text and page.text.strip() for page in pages):
            raise DocumentProcessingError(NO_READABLE_TEXT_MESSAGE)
        if not chunks or any(not _has_real_embedding(chunk.embedding) for chunk in chunks):
            raise DocumentProcessingError(EMBEDDING_UNAVAILABLE_MESSAGE)

        doc.status = "ready"
        doc.page_count = len(pages)
        doc.error_message = None
        if job is not None:
            job.status = "completed"
            job.last_error = None
            job_finished = True

    except Exception as exc:
        safe_message = _safe_error_message(exc)
        doc.status = "failed"
        doc.error_message = safe_message
        if job is not None:
            job.status = "failed"
            job.last_error = safe_message
            job_finished = True
        try:
            await _clear_existing_pages_and_chunks(db, doc.id)
        except Exception:
            logger.exception("Failed to clear pages/chunks for failed document %s", document_id)
        logger.exception("Document %s processing failed: %s", document_id, safe_message)
        raise
    finally:
        if job is not None and not job_finished:
            job.status = "failed"
            job.last_error = GENERIC_PROCESSING_ERROR_MESSAGE
        await db.commit()


async def process_document_background(document_id: str, db: AsyncSession | None = None) -> None:
    """Background-task entry point for document processing.

    When called from FastAPI BackgroundTasks (no db passed), creates its own
    async session via get_session_maker() and ensures it is properly closed.
    When called directly in tests (db passed), uses the provided session.

    Errors are logged but not re-raised so the caller's response is not affected.
    """
    from app.db.base import get_session_maker

    close_session = False
    if db is None:
        try:
            session_maker = get_session_maker()
            db = session_maker()
            close_session = True
        except Exception as exc:
            logger.exception("Failed to create DB session for background processing of %s: %s", document_id, exc)
            return

    exc_raised: Exception | None = None
    try:
        await process_document(db, document_id)
    except Exception as exc:
        exc_raised = exc
        logger.exception("Background processing failed for document %s: %s", document_id, exc)
    finally:
        if close_session and db is not None:
            try:
                await db.close()
            except Exception:
                pass
            db = None
        # Mark document as failed if an exception occurred and we still have a session
        if exc_raised is not None and db is not None:
            try:
                from sqlalchemy import select as sa_select
                from app.models.document import Document as DocModel
                stmt = sa_select(DocModel).where(DocModel.id == uuid.UUID(document_id))
                result = await db.execute(stmt)
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    doc.error_message = _safe_error_message(exc_raised)
                    await db.commit()
            except Exception:
                logger.exception("Failed to mark document %s as failed", document_id)


async def _get_document(db: AsyncSession, doc_id: uuid.UUID):
    stmt = select(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _clear_existing_pages_and_chunks(db: AsyncSession, doc_id: uuid.UUID) -> None:
    """Remove old pages and chunks for idempotent retries."""
    from sqlalchemy import delete
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc_id))
    await db.commit()


async def _delete_document_chunks(db: AsyncSession, doc_id: uuid.UUID) -> None:
    """Remove chunks so a failed embedding attempt persists no zero vectors."""
    from sqlalchemy import delete
    from app.models.document_chunk import DocumentChunk as ChunkModel
    await db.execute(delete(ChunkModel).where(ChunkModel.document_id == doc_id))
    await db.commit()


async def _start_processing_job(db: AsyncSession, doc_id: uuid.UUID):
    """Start a job and clear any stale running job for this document."""
    from sqlalchemy import update
    from app.models.processing_job import ProcessingJob
    await db.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.document_id == doc_id,
            ProcessingJob.status == "running",
        )
        .values(status="failed", last_error="Superseded by a new processing attempt")
    )
    job = ProcessingJob(document_id=doc_id, status="running", attempts=1)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def _document_storage_folder(doc: Document) -> str:
    """Return the private storage folder that belongs to this document."""
    expected = f"user/{doc.owner_id}/{doc.id}"
    if doc.storage_key and "/" in doc.storage_key:
        candidate = doc.storage_key.rsplit("/", 1)[0]
        if candidate.startswith(expected):
            return candidate
    return expected


def _store_page_image(doc: Document, page_number: int, image_bytes: bytes) -> str | None:
    """Upload a rendered OCR page image as JPEG under the document folder."""
    key = f"{_document_storage_folder(doc)}/page_{page_number}.jpg"
    try:
        storage = _get_storage_client()
        storage.storage.from_(settings.STORAGE_BUCKET).upload(
            key,
            image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        return key
    except Exception as exc:
        logger.warning(
            "Page image upload failed for doc %s page %d: %s",
            doc.id,
            page_number,
            exc,
        )
        return None


async def _process_pdf(db: AsyncSession, doc: Document) -> None:
    """Extract text from PDF using PyMuPDF text layer; falls back to OCR for blank pages."""
    fitz = _get_fitz()

    # Load PDF bytes from Supabase Storage
    storage = _get_storage_client()
    try:
        pdf_bytes = storage.storage.from_(settings.STORAGE_BUCKET).download(doc.storage_key)
    except Exception as exc:
        logger.warning("Failed to download PDF from storage for doc %s: %s", doc.id, exc)
        pdf_bytes = None

    if pdf_bytes is None:
        logger.warning("No PDF bytes available for doc %s — skipping text extraction", doc.id)
        return

    import io
    try:
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("Failed to open PDF for doc %s: %s", doc.id, exc)
        return

    try:
        page_count = len(pdf_doc)
        if page_count == 0:
            logger.warning("PDF %s has 0 pages", doc.id)
            return

        page_specs: list[tuple[int, object, str]] = []
        for page_num in range(page_count):
            page = pdf_doc[page_num]
            page_specs.append((page_num, page, page.get_text().strip()))

        pages_needing_ocr = sum(1 for _num, _page, text in page_specs if not text)
        _check_per_doc_ocr_limit(pages_needing_ocr)
        if pages_needing_ocr:
            await _check_daily_ocr_limit(db, doc.owner_id, pages_needing_ocr)

        ocr_provider = _get_ocr_provider() if pages_needing_ocr else None

        for page_num, page, text in page_specs:
            source = "text_layer"
            needs_review = False
            page_image_key = None

            # If text layer is empty, render page as image and OCR it
            if not text:
                try:
                    mat = fitz.Matrix(OCR_RENDER_DPI / 72, OCR_RENDER_DPI / 72)
                    pix = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes("jpeg", jpg_quality=85)
                    if ocr_provider:
                        ocr_result = await ocr_provider.transcribe_page(img_bytes, "image/jpeg")
                        text = ocr_result.text
                        source = "ocr"
                        needs_review = flag_needs_review(ocr_result)
                        if text.strip():
                            page_image_key = _store_page_image(doc, page_num + 1, img_bytes)
                    else:
                        text = ""
                        needs_review = True
                except OcrProviderError:
                    raise
                except Exception as exc:
                    logger.warning("OCR fallback failed for page %d of doc %s: %s", page_num + 1, doc.id, exc)
                    text = ""
                    needs_review = True

            doc_page = DocumentPage(
                document_id=doc.id,
                page_number=page_num + 1,
                text=text,
                source=source,
                needs_review=needs_review,
                page_image_key=page_image_key,
            )
            db.add(doc_page)

        await db.commit()
    finally:
        pdf_doc.close()


async def _process_images(
    db: AsyncSession,
    doc: Document,
    ocr_provider: OcrProvider | None = None,
) -> None:
    """Process uploaded images — runs OCR on each image page."""
    # Placeholder: iterate over doc's pages (already stored as image references)
    image_pages = await _get_image_pages(db, doc.id)

    if not image_pages:
        logger.warning("No image pages found for document %s", doc.id)
        return

    _check_per_doc_ocr_limit(len(image_pages))

    provider = ocr_provider or _get_ocr_provider()
    if provider is None:
        raise DocumentProcessingError(AI_NOT_CONFIGURED_MESSAGE)

    # Check daily limit before spending any OCR call
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


def _check_per_doc_ocr_limit(pages_to_process: int) -> None:
    """Raise when a file needs more OCR pages than the per-document cap."""
    limit = settings.OCR_LIMIT_PAGES_PER_DOC
    if not limit:
        return
    if pages_to_process > limit:
        raise DocumentProcessingError(
            f"This file needs OCR on {pages_to_process} pages, "
            f"which is over the limit of {limit} pages per file."
        )


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
        raise DocumentProcessingError(DAILY_OCR_LIMIT_MESSAGE)


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
    """Load image bytes and metadata from Supabase Storage for an image/multi_image document."""
    from app.core.config import settings

    # Find the document to get storage key prefix
    doc_stmt = select(Document).where(Document.id == doc_id)
    doc_result = await db.execute(doc_stmt)
    doc = doc_result.scalar_one_or_none()
    if not doc or not doc.storage_key:
        logger.warning("No storage key for document %s", doc_id)
        return []

    # storage_key is a file key (format: user/<owner_id>/<doc_id>/<filename>);
    # list() takes the containing folder, while returned names are relative to it.
    folder = doc.storage_key.rsplit("/", 1)[0]

    storage = _get_storage_client()
    try:
        files = storage.storage.from_(settings.STORAGE_BUCKET).list(folder)
    except Exception as exc:
        logger.warning("Storage list failed for %s: %s", folder, exc)
        return []

    pages: list[tuple[dict, bytes, str]] = []
    for f in sorted(files, key=lambda x: x.get("name", "")):
        name = f.get("name", "")
        if not name:
            continue
        try:
            storage_key = f"{folder}/{name}"
            data = storage.storage.from_(settings.STORAGE_BUCKET).download(storage_key)
            # Detect MIME from extension
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
            mime_type = mime_map.get(ext, f"image/{ext}")
            pages.append(({"storage_key": storage_key}, data, mime_type))
        except Exception as exc:
            logger.warning("Failed to download %s: %s", name, exc)

    return pages


def _get_storage_client():
    """Return Supabase storage client (service role)."""
    from app.core.config import settings
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def _count_pages(db: AsyncSession, doc_id: uuid.UUID) -> int:
    stmt = select(DocumentPage).where(DocumentPage.document_id == doc_id)
    result = await db.execute(stmt)
    return len(result.scalars().all())


CHARS_PER_TOKEN = 4
TINY_PAGE_RATIO = 0.3
BOUNDARY_SEARCH_RATIO = 0.5
SENTENCE_BOUNDARIES = (". ", "! ", "? ", ".\n", "!\n", "?\n")


def _chunk_limits(
    chunk_size: int | None = None, overlap: int | None = None
) -> tuple[int, int]:
    """Resolve token limits and validate their relationship."""
    target_tokens = settings.CHUNK_TARGET_TOKENS if chunk_size is None else chunk_size
    overlap_tokens = settings.CHUNK_OVERLAP_TOKENS if overlap is None else overlap
    if target_tokens <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if not 0 <= overlap_tokens < target_tokens:
        raise ValueError("overlap must be at least 0 and less than chunk_size")
    return target_tokens * CHARS_PER_TOKEN, overlap_tokens * CHARS_PER_TOKEN


def _find_boundary(text: str, start: int, hard_end: int) -> int:
    """Find a paragraph/sentence break in the second half of the window."""
    minimum = start + max(1, int((hard_end - start) * BOUNDARY_SEARCH_RATIO))

    paragraph = text.rfind("\n\n", minimum, hard_end)
    if paragraph != -1:
        return paragraph + 2

    best = -1
    best_length = 0
    for separator in SENTENCE_BOUNDARIES:
        index = text.rfind(separator, minimum, hard_end)
        if index > best:
            best = index
            best_length = len(separator)
    if best != -1:
        return best + best_length

    newline = text.rfind("\n", minimum, hard_end)
    if newline != -1:
        return newline + 1

    return hard_end


def _iter_chunks_with_spans(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[tuple[str, int, int]]:
    """Split text into chunks while retaining each chunk's character span."""
    chunk_chars, overlap_chars = _chunk_limits(chunk_size, overlap)
    chunks: list[tuple[str, int, int]] = []
    start = 0

    while start < len(text):
        hard_end = min(start + chunk_chars, len(text))
        end = hard_end
        if hard_end < len(text):
            end = _find_boundary(text, start, hard_end)
            if end <= start:
                end = hard_end

        chunk = text[start:end]
        if chunk.strip():
            chunks.append((chunk, start, end))

        if end >= len(text):
            break
        next_start = max(0, end - overlap_chars)
        start = next_start if next_start > start else end

    return chunks


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into token-aware chunks (approximate using chars)."""
    return [
        chunk
        for chunk, _start, _end in _iter_chunks_with_spans(text, chunk_size, overlap)
    ]


def _page_range_for_span(
    page_spans: list[tuple[int, int, int]], start: int, end: int
) -> tuple[int, int]:
    """Return the first and last page numbers whose text intersects the span."""
    intersecting = [
        page_number
        for page_number, page_start, page_end in page_spans
        if start < page_end and end > page_start
    ]
    if intersecting:
        return min(intersecting), max(intersecting)

    previous = page_spans[0][0] if page_spans else 1
    for page_number, page_start, page_end in page_spans:
        if start < page_start:
            return previous, previous
        if page_start <= start < page_end:
            return page_number, page_number
        previous = page_number
    return previous, previous


def _group_pages_for_chunks(
    pages: list[DocumentPage], chunk_chars: int
) -> list[list[DocumentPage]]:
    """Keep normal pages separate and merge tiny pages with a neighbor."""
    usable = [page for page in pages if (page.text or "").strip()]
    tiny_chars = max(1, int(chunk_chars * TINY_PAGE_RATIO))
    blocks: list[list[DocumentPage]] = []
    index = 0

    while index < len(usable):
        text = (usable[index].text or "").strip()
        if len(text) >= tiny_chars:
            blocks.append([usable[index]])
            index += 1
            continue

        if index == len(usable) - 1 and blocks:
            blocks[-1].append(usable[index])
            index += 1
            continue

        block = [usable[index]]
        block_chars = len(text)
        index += 1
        while index < len(usable) and block_chars < tiny_chars:
            next_text = (usable[index].text or "").strip()
            block.append(usable[index])
            block_chars += len(next_text) + 2
            index += 1
        blocks.append(block)

    return blocks


def _block_text_and_spans(
    block: list[DocumentPage],
) -> tuple[str, list[tuple[int, int, int]]]:
    """Join a page block and map character offsets back to page numbers."""
    texts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    offset = 0
    for page in block:
        text = (page.text or "").strip()
        if not text:
            continue
        if texts:
            offset += 2
        start = offset
        offset += len(text)
        texts.append(text)
        spans.append((page.page_number, start, offset))
    return "\n\n".join(texts), spans


async def create_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    pages: list[DocumentPage],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> None:
    """Create page-aware chunks, merging only tiny pages with a neighbor."""
    chunk_chars, _overlap_chars = _chunk_limits(chunk_size, overlap)
    blocks = _group_pages_for_chunks(pages, chunk_chars)

    for block in blocks:
        block_text, page_spans = _block_text_and_spans(block)
        if not block_text:
            continue
        for chunk_content, start, end in _iter_chunks_with_spans(
            block_text, chunk_size, overlap
        ):
            if not chunk_content.strip():
                continue
            page_start, page_end = _page_range_for_span(page_spans, start, end)

            chunk = DocumentChunk(
                document_id=document_id,
                page_start=page_start,
                page_end=page_end,
                content=chunk_content,
                token_count=len(chunk_content) // CHARS_PER_TOKEN,
            )
            db.add(chunk)

    await db.commit()


async def embed_chunks(
    db: AsyncSession,
    chunks: list[DocumentChunk],
    ocr_provider: OcrProvider | None = None,
) -> None:
    """Generate embeddings for chunks; raise instead of persisting zero vectors."""
    provider = ocr_provider or _get_ocr_provider()
    if provider is None:
        raise DocumentProcessingError(AI_NOT_CONFIGURED_MESSAGE)

    if not chunks:
        raise DocumentProcessingError(GENERIC_PROCESSING_ERROR_MESSAGE)
    if any(not chunk.content.strip() for chunk in chunks):
        raise DocumentProcessingError(GENERIC_PROCESSING_ERROR_MESSAGE)

    texts = [chunk.content for chunk in chunks]
    try:
        vectors = await provider.embed_texts(texts)
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", type(exc).__name__)
        raise DocumentProcessingError(EMBEDDING_UNAVAILABLE_MESSAGE) from exc

    if len(vectors) != len(chunks):
        raise DocumentProcessingError(EMBEDDING_UNAVAILABLE_MESSAGE)
    if any(not _has_real_embedding(vector) for vector in vectors):
        raise DocumentProcessingError(EMBEDDING_UNAVAILABLE_MESSAGE)

    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = vector

    await db.commit()


async def rerun_page_ocr(
    db: AsyncSession,
    page: DocumentPage,
    ocr_provider: OcrProvider | None = None,
) -> DocumentPage:
    """Re-read one stored page image with OCR, replacing text and chunks atomically.

    OCR and embeddings run before any database mutation. If either fails, the
    page text and its existing chunks are left untouched.
    """
    from sqlalchemy import delete

    provider = ocr_provider or _get_ocr_provider()
    if provider is None:
        raise DocumentProcessingError(AI_NOT_CONFIGURED_MESSAGE)

    image_key = page.page_image_key
    if not image_key:
        raise DocumentProcessingError("This page has no image to re-read.")

    try:
        image_bytes = _get_storage_client().storage.from_(settings.STORAGE_BUCKET).download(
            image_key
        )
    except Exception as exc:
        logger.warning("Page image download failed for page %s: %s", page.id, exc)
        raise DocumentProcessingError(OCR_RERUN_FAILED_MESSAGE) from exc
    if not image_bytes:
        raise DocumentProcessingError(OCR_RERUN_FAILED_MESSAGE)

    ext = image_key.rsplit(".", 1)[-1].lower() if "." in image_key else ""
    mime_type = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/png")

    try:
        ocr_result = await provider.transcribe_page(image_bytes, mime_type)
    except OcrProviderError:
        raise
    except Exception as exc:
        logger.warning("Re-run OCR failed for page %s: %s", page.id, exc)
        raise DocumentProcessingError(OCR_RERUN_FAILED_MESSAGE) from exc

    new_text = ocr_result.text or ""
    if not new_text.strip():
        raise DocumentProcessingError(OCR_RERUN_FAILED_MESSAGE)
    needs_review = flag_needs_review(ocr_result)

    chunk_contents = [chunk for chunk in chunk_text(new_text) if chunk.strip()]
    if not chunk_contents:
        raise DocumentProcessingError(OCR_RERUN_FAILED_MESSAGE)

    try:
        vectors = await provider.embed_texts(chunk_contents)
    except Exception as exc:
        logger.warning("Re-run OCR embedding failed for page %s: %s", page.id, exc)
        raise DocumentProcessingError(OCR_RERUN_EMBED_FAILED_MESSAGE) from exc
    if len(vectors) != len(chunk_contents) or any(
        not _has_real_embedding(vector) for vector in vectors
    ):
        raise DocumentProcessingError(OCR_RERUN_EMBED_FAILED_MESSAGE)

    try:
        page.text = new_text
        page.source = "ocr"
        page.user_edited = False
        page.needs_review = needs_review
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == page.document_id,
                DocumentChunk.page_start <= page.page_number,
                DocumentChunk.page_end >= page.page_number,
            )
        )
        for content, vector in zip(chunk_contents, vectors):
            db.add(
                DocumentChunk(
                    document_id=page.document_id,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    content=content,
                    token_count=len(content) // 4,
                    embedding=vector,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(page)
    return page


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


async def re_embed_page_background(
    page_id: uuid.UUID,
    new_text: str,
    db: AsyncSession | None = None,
) -> None:
    """Background entry point that owns its DB session when none is supplied."""
    from app.db.base import get_session_maker

    close_session = False
    if db is None:
        db = get_session_maker()()
        close_session = True

    try:
        await re_embed_page(db, page_id, new_text)
    except Exception:
        logger.exception("Background re-embedding failed for page %s", page_id)
    finally:
        if close_session:
            await db.close()


# Imports needed at runtime (avoid circular)
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.document_chunk import DocumentChunk  # noqa: E402
