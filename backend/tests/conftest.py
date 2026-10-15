"""Test fixtures — in-memory SQLite DB, fresh per test."""

import os
import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"

from app.db.base import Base, reset_db_for_testing  # noqa: E402
from app.models.profile import Profile  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.document_chunk import DocumentChunk  # noqa: E402
from app.models.processing_job import ProcessingJob  # noqa: E402


@pytest.fixture
async def db_session():
    """Fresh in-memory DB per test."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    reset_db_for_testing(test_engine)

    session = AsyncSession(test_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await test_engine.dispose()
        reset_db_for_testing(None)  # type: ignore[arg-type]


@pytest.fixture
async def test_user(db_session):
    user = Profile(sub="test-sub-001", email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_subject(db_session, test_user):
    subject = Subject(owner_id=test_user.id, name="Mathematics", description="Algebra and Calculus")
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)
    return subject
