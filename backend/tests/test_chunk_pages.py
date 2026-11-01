"""Tests for page-aware chunks and accurate page-range mapping."""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage, PageSource
from app.services.processing import create_chunks


async def _make_document(db_session, test_user, test_subject, page_texts):
    document = Document(
        owner_id=test_user.id,
        subject_id=test_subject.id,
        name="Three Pages.pdf",
        doc_type="pdf",
        status=DocumentStatus.READY,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    pages = [
        DocumentPage(
            document_id=document.id,
            page_number=index + 1,
            text=text,
            source=PageSource.TEXT_LAYER,
        )
        for index, text in enumerate(page_texts)
    ]
    db_session.add_all(pages)
    await db_session.commit()
    return document, pages


async def _chunks(db_session, document_id):
    result = await db_session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.page_start, DocumentChunk.page_end, DocumentChunk.content)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_chunk_inside_one_page(db_session, test_user, test_subject):
    document, pages = await _make_document(
        db_session, test_user, test_subject, ["A" * 8, "B" * 8, "C" * 8]
    )

    await create_chunks(db_session, document.id, pages, chunk_size=1, overlap=0)
    chunks = await _chunks(db_session, document.id)

    assert chunks
    assert all(chunk.page_start == chunk.page_end for chunk in chunks)
    assert {chunk.page_start for chunk in chunks} == {1, 2, 3}

    page_letters = {1: "A", 2: "B", 3: "C"}
    for chunk in chunks:
        letters = {char for char in chunk.content if char in "ABC"}
        assert letters == {page_letters[chunk.page_start]}


@pytest.mark.asyncio
async def test_normal_pages_stay_within_page(db_session, test_user, test_subject):
    document, pages = await _make_document(
        db_session, test_user, test_subject, ["A" * 8, "B" * 8, "C" * 8]
    )

    await create_chunks(db_session, document.id, pages, chunk_size=4, overlap=0)
    chunks = await _chunks(db_session, document.id)

    assert chunks
    assert all(chunk.page_start == chunk.page_end for chunk in chunks)
    assert {chunk.page_start for chunk in chunks} == {1, 2, 3}


@pytest.mark.asyncio
async def test_chunk_spans_three_pages(db_session, test_user, test_subject):
    document, pages = await _make_document(
        db_session, test_user, test_subject, ["A" * 8, "B" * 8, "C" * 8]
    )

    await create_chunks(db_session, document.id, pages, chunk_size=8, overlap=0)
    chunks = await _chunks(db_session, document.id)

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 3


@pytest.mark.asyncio
async def test_eight_pages_produce_page_local_chunks(
    db_session, test_user, test_subject
):
    page_texts = [
        f"page {number} " + ("word " * 160) for number in range(1, 9)
    ]
    assert all(750 <= len(text) <= 850 for text in page_texts)

    document, pages = await _make_document(
        db_session, test_user, test_subject, page_texts
    )
    await create_chunks(db_session, document.id, pages)
    chunks = await _chunks(db_session, document.id)

    assert len(chunks) == 8
    local = [chunk for chunk in chunks if chunk.page_start == chunk.page_end]
    assert len(local) / len(chunks) >= 0.8
    assert [chunk.page_start for chunk in local] == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.asyncio
async def test_tiny_page_merges_with_neighbor(db_session, test_user, test_subject):
    document, pages = await _make_document(
        db_session, test_user, test_subject, ["P" * 50, "Q" * 800]
    )

    await create_chunks(db_session, document.id, pages)
    chunks = await _chunks(db_session, document.id)

    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert "P" in chunks[0].content
    assert "Q" in chunks[0].content


@pytest.mark.asyncio
async def test_chunk_size_and_overlap_limits(db_session, test_user, test_subject):
    text = " ".join(
        f"Sentence {number} has enough words for a clean boundary."
        for number in range(200)
    )
    document, pages = await _make_document(
        db_session, test_user, test_subject, [text]
    )

    await create_chunks(db_session, document.id, pages)
    chunks = await _chunks(db_session, document.id)

    assert len(chunks) > 2
    target_chars = settings.CHUNK_TARGET_TOKENS * 4
    overlap_chars = settings.CHUNK_OVERLAP_TOKENS * 4
    assert all(len(chunk.content) <= target_chars for chunk in chunks)
    assert all(chunk.token_count <= settings.CHUNK_TARGET_TOKENS for chunk in chunks)
    assert all(
        chunk.content.rstrip().endswith(".")
        for chunk in chunks
    )

    for previous, current in zip(chunks, chunks[1:]):
        shared = 0
        for length in range(1, min(len(previous.content), len(current.content)) + 1):
            if previous.content[-length:] == current.content[:length]:
                shared = length
        assert shared <= overlap_chars
