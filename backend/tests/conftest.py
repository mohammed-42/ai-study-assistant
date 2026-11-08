"""Test fixtures — in-memory SQLite DB, fresh per test."""

import os
import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["SUPABASE_JWKS_URL"] = "https://test.supabase.co/auth/v1/.well-known/jwks.json"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["EMBEDDING_MODEL"] = "gemini-embedding-001"

from app.db.base import Base, reset_db_for_testing  # noqa: E402
from app.models.profile import Profile  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_page import DocumentPage  # noqa: E402
from app.models.document_chunk import DocumentChunk  # noqa: E402
from app.models.processing_job import ProcessingJob  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_gemini_rotation_state():
    from app.ai import gemini

    gemini.reset_rotation_state()
    yield
    gemini.reset_rotation_state()


@pytest.fixture
async def db_session():
    """Fresh in-memory DB per test."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(test_engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
