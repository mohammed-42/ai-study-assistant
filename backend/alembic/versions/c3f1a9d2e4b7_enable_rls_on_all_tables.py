"""enable row level security on all application tables

Revision ID: c3f1a9d2e4b7
Revises: b7d41e9a2c63
Create Date: 2026-11-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3f1a9d2e4b7'
down_revision: Union[str, Sequence[str], None] = 'b7d41e9a2c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES: tuple[str, ...] = (
    "profiles",
    "subjects",
    "documents",
    "document_pages",
    "document_chunks",
    "processing_jobs",
    "chat_sessions",
    "chat_messages",
    "notes",
    "quizzes",
    "quiz_questions",
    "quiz_attempts",
    "quiz_responses",
    "study_plans",
    "study_tasks",
)


def upgrade() -> None:
    """Enable RLS on every application table."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    """Disable RLS on every application table."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
