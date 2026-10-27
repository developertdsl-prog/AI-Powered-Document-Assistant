"""Add pgvector support and the chunk embedding column.

Enables the pgvector extension, adds ``document_chunks.embedding`` as a
fixed-width ``vector`` column, and creates an HNSW cosine-similarity index
for retrieval (Phase 3.3). The extension and index are PostgreSQL-only; the
column itself is added on every dialect so SQLite test databases keep
working.

Revision ID: 0003_embeddings
Revises: 0002_document_pages
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# Must match app.core.config.EMBEDDING_DIMENSIONS; the number is frozen here
# so historical migrations never change behaviour.
EMBEDDING_DIMENSIONS = 1536

revision: str = "0003_embeddings"
down_revision: str | None = "0002_document_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            Vector(EMBEDDING_DIMENSIONS),
            nullable=True,
        ),
    )

    if connection.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")

    op.drop_column("document_chunks", "embedding")
