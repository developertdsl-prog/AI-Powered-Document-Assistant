"""Embedding providers for document chunks.

The retrieval pipeline (Phase 3.3) compares vectors, so every chunk needs an
embedding at processing time. Providers implement :class:`EmbeddingProvider`
and are selected with ``EMBEDDING_PROVIDER``:

- ``auto``    use OpenAI when ``OPENAI_API_KEY`` is set, otherwise the local
              deterministic hash provider (the development default).
- ``openai``  OpenAI-compatible ``/v1/embeddings`` endpoint; fails when the
              API key is missing.
- ``hash``    local, offline, deterministic vectors for tests and development.
- ``none``    skip embedding generation; chunks are stored without vectors.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import httpx

from app.core.config import EMBEDDING_DIMENSIONS, Settings

logger = logging.getLogger(__name__)

PROVIDER_CHOICES = ("auto", "openai", "hash", "none")


class EmbeddingError(Exception):
    """Raised when embeddings cannot be produced."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """A backend that turns text into fixed-width vectors."""

    name: str
    dimensions: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class HashEmbeddingProvider:
    """Deterministic, offline vectors derived from the SHA-256 of the text.

    Similar texts do not produce similar vectors, so this provider never
    yields meaningful similarity search results. It exists so that the
    pipeline, tests, and local development work without an API key.
    """

    name = "hash"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        if dimensions <= 0:
            raise EmbeddingError("Embedding dimensions must be positive.")
        self.dimensions = dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        # Expand SHA-256 digests until the vector is full width, then map
        # unsigned bytes to [-1, 1] and normalize.
        block = text.encode("utf-8")
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(counter.to_bytes(4, "big") + block).digest()
            for offset in range(0, len(digest), 4):
                raw = int.from_bytes(digest[offset : offset + 4], "big")
                values.append(raw / 0xFFFFFFFF * 2 - 1)
                if len(values) == self.dimensions:
                    break
            counter += 1
        return _normalize(values)


class OpenAIEmbeddingProvider:
    """OpenAI-compatible ``/embeddings`` client with batching."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        dimensions: int = EMBEDDING_DIMENSIONS,
        batch_size: int = 100,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingError("An API key is required for the OpenAI provider.")
        if dimensions <= 0:
            raise EmbeddingError("Embedding dimensions must be positive.")
        if batch_size <= 0:
            raise EmbeddingError("Embedding batch size must be positive.")

        self._api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self._url = base_url.rstrip("/") + "/embeddings"
        self._timeout = timeout_seconds
        self._transport = transport

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        # One client per call keeps connections pooled across batches without
        # leaving sockets behind after processing finishes.
        with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
            for start in range(0, len(texts), self.batch_size):
                batch = list(texts[start : start + self.batch_size])
                vectors.extend(self._embed_batch(client, batch))
        return vectors

    def _embed_batch(self, client: httpx.Client, batch: list[str]) -> list[list[float]]:
        body: dict[str, object] = {"model": self.model, "input": batch}
        # Only the text-embedding-3-* models accept a custom width.
        if self.model.startswith("text-embedding-3-"):
            body["dimensions"] = self.dimensions

        try:
            response = client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingError("The embedding provider could not be reached.") from exc

        if response.status_code >= 400:
            raise EmbeddingError(f"The embedding provider returned HTTP {response.status_code}.")

        try:
            payload = response.json()
            items = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [[float(v) for v in item["embedding"]] for item in items]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError("The embedding provider returned an unexpected response.") from exc

        for vector in vectors:
            if len(vector) != self.dimensions:
                raise EmbeddingError(
                    "The embedding provider returned vectors of width "
                    f"{len(vector)}, expected {self.dimensions}."
                )

        return vectors


def get_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Build the provider selected by ``settings.embedding_provider``.

    Returns ``None`` when embeddings are disabled. Raises
    :class:`EmbeddingError` for an unknown name or a missing API key.
    """

    choice = settings.embedding_provider.strip().lower()

    if choice == "none":
        return None

    if choice == "hash":
        return HashEmbeddingProvider()

    if choice == "openai":
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")
        return _openai_provider(settings)

    if choice == "auto":
        if settings.openai_api_key:
            return _openai_provider(settings)
        logger.info("OPENAI_API_KEY is not set; using the offline hash embedding provider.")
        return HashEmbeddingProvider()

    raise EmbeddingError(
        f"Unknown embedding provider '{settings.embedding_provider}'. "
        f"Expected one of: {', '.join(PROVIDER_CHOICES)}."
    )


def _openai_provider(settings: Settings) -> OpenAIEmbeddingProvider:
    assert settings.openai_api_key is not None
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
        base_url=settings.openai_base_url,
        batch_size=settings.embedding_batch_size,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
