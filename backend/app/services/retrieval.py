"""Similarity search over embedded document chunks (Phase 3.3).

Retrieval takes a query vector and returns the closest chunks of a single
document so answer generation (Phase 3.4) can quote them:

- scoring runs in Python, which keeps the service identical on PostgreSQL
  and on the SQLite test database;
- ``document_chunks.embedding`` already carries the HNSW cosine index from
  migration ``0003_embeddings``, so the comparison can move to a
  database-side ``<=>`` operator later without a schema change.
"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentChunk


class RetrievalError(Exception):
    """Raised when a similarity search cannot be executed."""


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return the cosine similarity of two equally sized vectors."""

    if not left or not right:
        raise RetrievalError("Vectors must not be empty.")
    if len(left) != len(right):
        raise RetrievalError(
            f"Vector width mismatch: {len(left)} versus {len(right)}."
        )

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def search_document_chunks(
    db: Session,
    *,
    document_id: UUID,
    query_vector: list[float],
    limit: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Return the closest embedded chunks of one document, best first.

    Chunks stored without an embedding (``EMBEDDING_PROVIDER=none``) are
    skipped instead of scored as unrelated. Ownership and processing status
    are enforced by the caller before this runs.
    """

    if limit < 1:
        raise RetrievalError("The result limit must be at least 1.")
    if not query_vector:
        raise RetrievalError("The query vector must not be empty.")

    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()

    scored = [
        (chunk, cosine_similarity(list(chunk.embedding), query_vector))
        for chunk in chunks
        if chunk.embedding is not None
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
