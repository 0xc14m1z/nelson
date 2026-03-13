"""Deterministic fake provider for testing.

``FakeProvider`` simulates all provider behaviors needed by the
consensus test suite without making real API calls. It can return
configured responses, stream configured deltas, or raise configured
errors.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from nelson.core.errors import NelsonError
from nelson.protocols.domain import UsageSnapshot
from nelson.providers.base import ProviderResponse, ProviderStream, StreamDelta


class FakeStream:
    """Async iterator over pre-configured deltas with optional usage.

    Implements the ``ProviderStream`` protocol so that the consensus
    engine can consume it identically to a real provider stream.

    If ``error`` is provided, it is raised on the first ``__anext__()``
    call instead of yielding deltas — used when the provider is
    configured to simulate failures during streaming.
    """

    def __init__(
        self,
        deltas: list[StreamDelta],
        stream_usage: UsageSnapshot | None = None,
        *,
        error: NelsonError | None = None,
    ) -> None:
        self._deltas = deltas
        self._stream_usage = stream_usage
        self._error = error
        self._index = 0

    def __aiter__(self) -> AsyncIterator[StreamDelta]:
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> StreamDelta:
        """Return the next pre-configured delta, or raise error if configured."""
        if self._error is not None:
            raise self._error
        if self._index >= len(self._deltas):
            raise StopAsyncIteration
        delta = self._deltas[self._index]
        self._index += 1
        return delta

    async def usage(self) -> UsageSnapshot | None:
        """Return the pre-configured usage snapshot."""
        return self._stream_usage


class FakeProvider:
    """Deterministic fake provider for consensus and failure testing.

    Configure with responses, stream deltas, and/or an error to simulate
    the full range of provider behaviors:

    - **responses**: list of ``ProviderResponse`` to return from ``invoke()``,
      consumed in order (FIFO). If exhausted, raises ``IndexError``.
    - **stream_deltas**: list of delta lists for ``stream()``, consumed in
      order (FIFO). Each inner list is the sequence of deltas for one stream.
    - **stream_usage**: optional ``UsageSnapshot`` returned from stream usage.
    - **error**: if set, ``invoke()`` raises this error instead of returning
      a response. Takes precedence over responses.
    """

    def __init__(
        self,
        *,
        responses: list[ProviderResponse] | None = None,
        stream_deltas: list[list[StreamDelta]] | None = None,
        stream_usage: UsageSnapshot | None = None,
        error: NelsonError | None = None,
    ) -> None:
        self._responses = list(responses) if responses else []
        self._stream_deltas = list(stream_deltas) if stream_deltas else []
        self._stream_usage = stream_usage
        self._error = error
        self._invoke_count = 0
        self._stream_count = 0

    async def invoke(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object] | None = None,
        timeout_seconds: float = 60.0,
    ) -> ProviderResponse:
        """Return the next pre-configured response, or raise the configured error."""
        if self._error is not None:
            raise self._error

        if self._invoke_count >= len(self._responses):
            msg = (
                f"FakeProvider has no more responses "
                f"(called {self._invoke_count + 1} times, "
                f"configured {len(self._responses)} responses)"
            )
            raise IndexError(msg)

        response = self._responses[self._invoke_count]
        self._invoke_count += 1
        return response

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float = 60.0,
    ) -> ProviderStream:
        """Return a FakeStream over pre-configured deltas."""
        if self._error is not None:
            # Error-on-first-iteration stream — deltas are irrelevant
            return FakeStream([], error=self._error)

        if self._stream_count >= len(self._stream_deltas):
            # Return an empty stream if no more deltas configured
            return FakeStream([], self._stream_usage)

        deltas = self._stream_deltas[self._stream_count]
        self._stream_count += 1
        return FakeStream(deltas, self._stream_usage)
