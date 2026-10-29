"""Chat completion transport for grounded answer generation (Phase 3.4).

The answer service owns prompt assembly, grounding, and citations; this module
only carries messages to an OpenAI-compatible ``/chat/completions`` endpoint
and back. Provider *selection* (``LLM_PROVIDER``) lives in
:mod:`app.services.answers` because the offline extractive provider does not
speak chat messages at all.

- keys are backend-only settings and never appear in a response;
- requests run with ``temperature`` 0 so repeated questions are reproducible;
- every failure mode (network, HTTP status, malformed payload, empty answer)
  raises :class:`LLMError` so the API can answer with ``503`` instead of a
  stack trace.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import httpx

from app.core.config import Settings

LLM_TIMEOUT_FALLBACK_SECONDS = 60.0
LLM_MAX_TOKENS_DEFAULT = 700


class LLMError(Exception):
    """Raised when a chat completion cannot be produced."""


@runtime_checkable
class ChatProvider(Protocol):
    """A backend that turns chat messages into a single assistant reply."""

    name: str

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        """Return the assistant message for the given chat messages."""
        ...


class OpenAIChatProvider:
    """OpenAI-compatible ``/chat/completions`` client."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = LLM_TIMEOUT_FALLBACK_SECONDS,
        max_tokens: int = LLM_MAX_TOKENS_DEFAULT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("An API key is required for the OpenAI answer provider.")
        if not model.strip():
            raise LLMError("A model name is required for the OpenAI answer provider.")

        self.model = model
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
        self._transport = transport

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        if not messages:
            raise LLMError("At least one message is required.")

        body: dict[str, object] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "temperature": 0,
        }
        if self._max_tokens > 0:
            body["max_tokens"] = self._max_tokens

        with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
            try:
                response = client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
            except httpx.HTTPError as exc:
                raise LLMError("The answer provider could not be reached.") from exc

        if response.status_code >= 400:
            raise LLMError(f"The answer provider returned HTTP {response.status_code}.")

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise LLMError("The answer provider returned an unexpected response.") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("The answer provider returned an empty answer.")

        return content.strip()


def get_chat_provider(settings: Settings) -> ChatProvider:
    """Build the OpenAI-compatible chat provider from the settings.

    Raises :class:`LLMError` when the API key is missing, so a configuration
    problem surfaces as a service error instead of an empty answer.
    """

    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is required to use the LLM answer provider.")

    return OpenAIChatProvider(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_tokens,
    )
