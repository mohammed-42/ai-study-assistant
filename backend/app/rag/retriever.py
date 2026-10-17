"""RAG retrieval service for vector search."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from vector search."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_start: int
    page_end: int
    content: str
    similarity: float
    document_name: str = ""
    owner_id: uuid.UUID | None = None


async def retrieve_chunks(
    db: AsyncSession,
    query_embedding: list[float],
    owner_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    min_similarity: float = 0.6,
) -> list[RetrievalResult]:
    """Retrieve relevant chunks using vector similarity search.
    
    Uses SQLAlchemy ORM to properly handle pgvector embedding types.
    Falls back to manual cosine similarity calculation for SQLite.
    """
    # Build base query
    stmt = (
        select(DocumentChunk, Document.name.label("doc_name"), Document.owner_id.label("doc_owner_id"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.owner_id == owner_id,
            Document.status == "ready",
            DocumentChunk.embedding.isnot(None),
        )
    )
    
    if subject_id:
        stmt = stmt.where(Document.subject_id == subject_id)
    
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    if not rows:
        logger.info("No chunks found for retrieval")
        return []
    
    # Calculate cosine similarity for each row
    results = []
    for chunk, doc_name, doc_owner_id in rows:
        embedding = chunk.embedding
        if not embedding:
            continue
        
        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(query_embedding, embedding))
        norm_query = sum(a * a for a in query_embedding) ** 0.5
        norm_embedding = sum(b * b for b in embedding) ** 0.5
        
        if norm_query > 0 and norm_embedding > 0:
            similarity = dot_product / (norm_query * norm_embedding)
        else:
            similarity = 0.0
        
        if similarity >= min_similarity:
            results.append(RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content=chunk.content,
                similarity=similarity,
                document_name=doc_name or "",
                owner_id=doc_owner_id,
            ))
    
    # Sort by similarity (descending) and return top_k
    results.sort(key=lambda x: x.similarity, reverse=True)
    return results[:top_k]
