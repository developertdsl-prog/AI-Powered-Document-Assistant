"""Split extracted pages into retrieval-ready text chunks.

Chunks are the unit of storage and search for the retrieval pipeline
(Phase 3). The splitter is paragraph-aware: it first groups lines into
paragraphs, then packs paragraphs into chunks of roughly ``chunk_size``
characters with ``overlap`` characters shared between neighbours so that
sentences spanning a boundary are still retrievable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.extraction import ExtractedDocument, ExtractedPage

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


class ChunkingError(Exception):
    """Raised when a document cannot be split into chunks."""


@dataclass(frozen=True)
class TextChunk:
    """One retrieval chunk with its position in the source document."""

    chunk_index: int
    content: str
    page_number: int | None
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Approximate token count without a tokenizer dependency.

    Uses the common heuristic of ~4 characters per token, with a floor of
    one token for non-empty text.
    """

    if not text:
        return 0
    return max(1, round(len(text) / 4))


def _paragraphs(page: ExtractedPage) -> list[str]:
    """Split one page's content into non-empty paragraphs."""

    parts = [part.strip() for part in page.content.split("\n\n")]
    return [part for part in parts if part]


def _split_long_paragraph(paragraph: str, size: int) -> list[str]:
    """Hard-split a paragraph that alone exceeds the chunk size."""

    pieces: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + size, len(paragraph))
        piece = paragraph[start:end].strip()
        if piece:
            pieces.append(piece)
        start = end
    return pieces


def _pack(pieces: list[tuple[str, int]], size: int, overlap: int) -> list[list[tuple[str, int]]]:
    """Greedily pack ``(text, page_number)`` pieces into overlapping chunks."""

    groups: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_length = 0

    for text, page_number in pieces:
        added_length = len(text) + (2 if current else 0)

        if current and current_length + added_length > size:
            groups.append(current)
            # Carry an overlap window forward from the tail of the group.
            carried: list[tuple[str, int]] = []
            carried_length = 0
            for carried_text, carried_page in reversed(current):
                if carried_length + len(carried_text) > overlap:
                    break
                carried.insert(0, (carried_text, carried_page))
                carried_length += len(carried_text) + 2
            current = carried
            current_length = carried_length
            added_length = len(text) + (2 if current else 0)
            if current and current_length + added_length > size:
                # Overlap alone exceeds the chunk size; start fresh.
                current = []
                current_length = 0

        current.append((text, page_number))
        current_length += len(text) + (2 if len(current) > 1 else 0)

    if current:
        groups.append(current)

    return groups


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Split extracted pages into ordered, overlapping chunks.

    Raises :class:`ChunkingError` for invalid configuration or when no
    chunkable text is found.
    """

    if chunk_size <= 0:
        raise ChunkingError("chunk_size must be positive.")
    if chunk_overlap < 0:
        raise ChunkingError("chunk_overlap cannot be negative.")
    if chunk_overlap >= chunk_size:
        raise ChunkingError("chunk_overlap must be smaller than chunk_size.")

    pieces: list[tuple[str, int]] = []
    for page in pages:
        for paragraph in _paragraphs(page):
            if len(paragraph) > chunk_size:
                pieces.extend(
                    (piece, page.page_number)
                    for piece in _split_long_paragraph(paragraph, chunk_size)
                )
            else:
                pieces.append((paragraph, page.page_number))

    if not pieces:
        return []

    groups = _pack(pieces, chunk_size, chunk_overlap)

    chunks: list[TextChunk] = []
    for index, group in enumerate(groups, start=0):
        content = "\n\n".join(text for text, _ in group)
        page_numbers = {page_number for _, page_number in group}
        chunks.append(
            TextChunk(
                chunk_index=index,
                content=content,
                page_number=min(page_numbers),
                token_count=estimate_tokens(content),
                metadata={
                    "page_numbers": sorted(page_numbers),
                    "character_count": len(content),
                    "paragraph_count": len(group),
                    "spans_pages": len(page_numbers) > 1,
                },
            )
        )

    return chunks


def chunk_document(
    document: ExtractedDocument,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Convenience wrapper around :func:`chunk_pages`."""

    return chunk_pages(
        document.pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
