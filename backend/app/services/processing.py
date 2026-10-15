"""Processing pipeline for document ingestion."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

# Lazy import of fitz (PyMuPDF) to avoid DLL issues in test env
_fitz: Optional[type] = None


def _get_fitz():
    global _fitz
    if _fitz is None:
        try:
            import fitz
            _fitz = fitz
        except ImportError as e:
            raise ImportError(f"PyMuPDF (fitz) not available: {e}") from e
    return _fitz

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage, PageSource
from app.models.document_chunk import DocumentChunk
from app.models.processing_job import ProcessingJob, JobStatus


async def process_document(db: AsyncSession, document_id: str) -> None:
    """Process a document: extract text, create pages, chunk, embed."""
    from uuid import UUID
    
    doc = await _get_document(db, UUID(document_id))
    if doc is None:
        return
    
    doc.status = DocumentStatus.PROCESSING
    await db.commit()
    
    try:
        if doc.doc_type == "pdf":
            await _process_pdf(db, doc)
        elif doc.doc_type in ("image", "multi_image"):
            await _process_images(db, doc)
        else:
            raise ValueError(f"unknown doc_type: {doc.doc_type}")
        
        doc.status = DocumentStatus.READY
        doc.page_count = await _count_pages(db, doc.id)
        
    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)[:2000]
        raise
    finally:
        await db.commit()


async def _get_document(db: AsyncSession, doc_id: "uuid.UUID"):
    import uuid
    stmt = select(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _process_pdf(db: AsyncSession, doc: Document) -> None:
    """Extract text from PDF using PyMuPDF."""
    # TODO: Load file from storage
    # For now, placeholder
    page_count = 0  # TODO: Get actual page count
    
    for page_num in range(page_count):
        # TODO: Extract text from page
        page_text = ""  # Placeholder
        source = PageSource.TEXT_LAYER
        
        page = DocumentPage(
            document_id=doc.id,
            page_number=page_num + 1,
            text=page_text,
            source=source,
            needs_review=len(page_text) < 50,  # Flag short pages for review
        )
        db.add(page)
    
    await db.commit()


async def _process_images(db: AsyncSession, doc: Document) -> None:
    """Process uploaded images."""
    # TODO: Load images from storage
    # Placeholder
    pass


async def _count_pages(db: AsyncSession, doc_id: "uuid.UUID") -> int:
    stmt = select(DocumentPage).where(DocumentPage.document_id == doc_id)
    result = await db.execute(stmt)
    return len(result.scalars().all())


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into token-aware chunks (approximate using chars)."""
    # Rough approximation: ~4 chars per token
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


async def create_chunks(db: AsyncSession, document_id: "uuid.UUID", pages: list[DocumentPage]) -> None:
    """Create document chunks from pages."""
    all_text = "\n\n".join(p.text for p in pages)
    chunks = chunk_text(all_text)
    
    for i, chunk_text in enumerate(chunks):
        # Determine which pages this chunk spans
        total_pages = len(pages)
        chunk_size = len(all_text) / max(len(chunks), 1)
        page_start = int(i * chunk_size / max(len(pages), 1))
        page_end = min(total_pages, page_start + 1)
        
        chunk = DocumentChunk(
            document_id=document_id,
            page_start=page_start + 1,
            page_end=page_end + 1,
            content=chunk_text,
            token_count=len(chunk_text) // 4,  # Approximate
        )
        db.add(chunk)
    
    await db.commit()


async def embed_chunks(db: AsyncSession, chunks: list[DocumentChunk]) -> None:
    """Generate embeddings for chunks."""
    # TODO: Call Gemini embedding API
    # For now, placeholder - set empty embeddings
    for chunk in chunks:
        chunk.embedding = [0.0] * 768  # Placeholder
    await db.commit()
