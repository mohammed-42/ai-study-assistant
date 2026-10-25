"""add hnsw embedding index

Revision ID: b7d41e9a2c63
Revises: e34c954767af
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d41e9a2c63'
down_revision: Union[str, Sequence[str], None] = 'e34c954767af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create an HNSW cosine index on document_chunks.embedding."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Drop the HNSW cosine index on document_chunks.embedding."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
