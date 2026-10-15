from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings_instance


class Base(DeclarativeBase):
    pass


def _get_engine():
    """Lazy engine creation — reads current env at call time."""
    settings = get_settings_instance()
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


def _get_session_maker():
    settings = get_settings_instance()
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Module-level defaults (for production; tests override via env)
_engine = None
_session_maker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def get_session_maker():
    global _session_maker
    if _session_maker is None:
        _session_maker = _get_session_maker()
    return _session_maker


async def get_db() -> AsyncSession:
    maker = get_session_maker()
    async with maker() as session:
        yield session


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def reset_db_for_testing(test_engine):
    """Replace engine/session maker with test-specific ones."""
    global _engine, _session_maker
    _engine = test_engine
    TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    _session_maker = TestSession
