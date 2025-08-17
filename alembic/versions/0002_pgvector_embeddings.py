"""
Add pgvector extension and embedding support

Revision ID: 0002_pgvector_embeddings
Revises: 0001_initial
Create Date: 2025-08-15 12:52:36
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_pgvector_embeddings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add optional grouping for chunked entries
    op.add_column("memory_entries", sa.Column("group_id", sa.Text(), nullable=True))
    op.create_index("idx_memory_group_id", "memory_entries", ["group_id"]) 

    # Add embedding column with dimension 384 (MiniLM-L6)
    op.execute("ALTER TABLE memory_entries ADD COLUMN IF NOT EXISTS embedding vector(384)")

    # Create an IVFFLAT index for cosine similarity on the embedding column
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_embedding_cosine ON memory_entries USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # Drop vector index if present
    op.execute("DROP INDEX IF EXISTS idx_memory_embedding_cosine")

    # Drop group_id index and column
    op.drop_index("idx_memory_group_id", table_name="memory_entries")
    op.drop_column("memory_entries", "group_id")

    # Drop embedding column
    op.execute("ALTER TABLE memory_entries DROP COLUMN IF EXISTS embedding")

    # Note: we intentionally do not drop the 'vector' extension
    # as it may be used by other objects/schemas.
