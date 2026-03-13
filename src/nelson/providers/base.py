"""Provider interface and shared types for model invocations.

The ``Provider`` runtime-checkable Protocol defines the contract that
all provider implementations (OpenRouter, fake) must satisfy. The
consensus engine depends only on this Protocol, never on concrete
provider classes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import FinishReason


@dataclass
class ProviderResponse:
    """Response from a non-streaming provider invocation."""

    content: str
    """Raw text content returned by the model."""

    parsed: dict[str, object] | None = None
    """Parsed structured output, if the response was JSON."""

    finish_reason: FinishReason = FinishReason.STOP
    """Why the model stopped generating tokens."""

    usage: UsageSnapshot | None = None
    """Token and cost usage for this invocation."""


@dataclass
class StreamDelta:
    """A single streaming chunk from a provider."""

    text: str
    """Text content of this chunk."""

    delta_index: int
    """Zero-based index of this chunk in the stream."""


class ProviderStream(Protocol):
    """Async iterator over streaming deltas with post-stream usage access.

    Implementations must support ``async for delta in stream`` to iterate
    over deltas, and ``await stream.usage()`` to get usage data after the
    stream is fully consumed.
    """

    def __aiter__(self) -> AsyncIterator[StreamDelta]:
        """Iterate over streaming deltas."""
        ...

    async def __anext__(self) -> StreamDelta:
        """Return the next streaming delta."""
        ...

    async def usage(self) -> UsageSnapshot | None:
        """Return usage data after the stream is fully consumed."""
        ...


@runtime_checkable
class Provider(Protocol):
    """Provider interface for model invocations.

    All provider implementations must satisfy this Protocol. The consensus
    engine uses only this interface, keeping it provider-agnostic.
    """

    async def invoke(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object] | None = None,
        timeout_seconds: float = 60.0,
    ) -> ProviderResponse:
        """Send a non-streaming request and return the complete response.

        Args:
            model: OpenRouter model ID (e.g. 'openai/gpt-4.1').
            messages: Chat messages in OpenAI format.
            response_schema: Optional JSON Schema for structured output.
            timeout_seconds: Maximum seconds to wait for a response.

        Raises:
            ProviderTimeoutError: If the call exceeds timeout_seconds.
            ProviderTransportError: If a network or transport error occurs.
            ProviderAuthError: If the API key is invalid or unauthorized.
            StructuredOutputInvalidError: If structured output validation fails.
        """
        ...

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float = 60.0,
    ) -> ProviderStream:
        """Start a streaming request and return a ProviderStream.

        The returned stream yields ``StreamDelta`` objects as they arrive.
        After iteration completes, ``await stream.usage()`` returns the
        usage data (if the provider reported it).

        Args:
            model: OpenRouter model ID.
            messages: Chat messages in OpenAI format.
            timeout_seconds: Maximum seconds to wait for the stream.
        """
        ...


# Re-export concrete implementations so tests can import from base
# These are lazy imports to avoid circular dependencies — the actual
# classes are defined in their own modules.
def __getattr__(name: str) -> type:
    """Lazy import of FakeProvider and OpenRouterProvider for convenience."""
    if name == "FakeProvider":
        from nelson.providers.fake import FakeProvider

        return FakeProvider
    if name == "OpenRouterProvider":
        from nelson.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
