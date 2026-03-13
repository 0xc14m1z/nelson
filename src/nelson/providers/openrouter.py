"""OpenRouter provider — OpenAI SDK adapter.

Implements the ``Provider`` protocol for OpenRouter's chat completions
API using the OpenAI Python SDK pointed at OpenRouter's base URL.
Supports both non-streaming and streaming modes, with usage extraction.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from typing import cast

import openai
from openai import AsyncStream
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

from nelson.core.errors import (
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import FinishReason
from nelson.providers.base import ProviderResponse, ProviderStream, StreamDelta

# OpenRouter is OpenAI-API-compatible — the SDK just needs a different base URL.
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _translate_error(
    exc: openai.APIError,
) -> ProviderAuthError | ProviderTimeoutError | ProviderTransportError:
    """Map OpenAI SDK exceptions to Nelson domain errors.

    Ordering matters: ``APITimeoutError`` is a subclass of
    ``APIConnectionError``, so it must be checked first.
    """
    if isinstance(exc, openai.APITimeoutError):
        return ProviderTimeoutError(f"OpenRouter request timed out: {exc}")
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ProviderAuthError(f"OpenRouter rejected the API key: {exc}")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderTransportError(f"OpenRouter connection failed: {exc}")
    # APIStatusError covers rate limits (429), server errors (5xx), etc.
    status = getattr(exc, "status_code", "?")
    return ProviderTransportError(f"OpenRouter request failed (HTTP {status}): {exc}")


def _extract_usage(usage: CompletionUsage | None) -> UsageSnapshot | None:
    """Convert an OpenAI SDK ``CompletionUsage`` to our domain ``UsageSnapshot``.

    Returns None if the SDK did not include usage data in the response.
    """
    if usage is None:
        return None
    return UsageSnapshot(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )


class OpenRouterProvider:
    """Provider implementation for OpenRouter using the OpenAI Python SDK.

    Points ``AsyncOpenAI`` at OpenRouter's base URL. Automatic retries are
    disabled — Nelson controls retry policy at the orchestration layer
    (PYTHON_ENGINEERING_STANDARDS §6.3).
    """

    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=_OPENROUTER_BASE_URL,
            # Disable automatic retries — Nelson manages retry policy in the
            # consensus engine, not hidden inside the provider adapter.
            max_retries=0,
        )

    async def invoke(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object] | None = None,
        timeout_seconds: float = 60.0,
    ) -> ProviderResponse:
        """Send a non-streaming chat completion request to OpenRouter."""
        # Cast messages from our Protocol's dict format to the SDK's TypedDict
        # union. The runtime shape is identical; the cast bridges the type gap
        # at this external library boundary (§4.2).
        sdk_messages = cast(list[ChatCompletionMessageParam], messages)

        try:
            if response_schema is not None:
                # TODO(phase-6): OpenRouter expects json_schema to contain
                # {"name": "...", "strict": true, "schema": {...}}, not a bare
                # schema. The caller contract needs a design decision when the
                # consensus engine starts using structured output.
                completion = await self._client.chat.completions.create(
                    model=model,
                    messages=sdk_messages,
                    response_format={  # type: ignore[arg-type]  # dict matches SDK TypedDict at runtime
                        "type": "json_schema",
                        "json_schema": response_schema,
                    },
                    timeout=timeout_seconds,
                )
            else:
                completion = await self._client.chat.completions.create(
                    model=model,
                    messages=sdk_messages,
                    timeout=timeout_seconds,
                )
        except openai.APIError as exc:
            raise _translate_error(exc) from exc

        # Extract content and finish reason from the typed response object.
        # The SDK returns Pydantic models, not dicts — no manual parsing needed.
        content = ""
        finish_reason = FinishReason.STOP
        if completion.choices:
            content = completion.choices[0].message.content or ""
            # Coerce the API string into the enum — unknown values fall back
            # to STOP so callers always get a valid FinishReason.
            raw_reason = completion.choices[0].finish_reason or "stop"
            try:
                finish_reason = FinishReason(raw_reason)
            except ValueError:
                finish_reason = FinishReason.STOP

        usage = _extract_usage(completion.usage)

        # Only attempt JSON parsing here. Schema validation and
        # StructuredOutputInvalidError are raised by the consensus engine
        # (Phase 6/8), not the provider layer.
        parsed: dict[str, object] | None = None
        if response_schema is not None and content:
            with contextlib.suppress(json.JSONDecodeError):
                parsed = json.loads(content)

        return ProviderResponse(
            content=content,
            parsed=parsed,
            finish_reason=finish_reason,
            usage=usage,
        )

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        timeout_seconds: float = 60.0,
    ) -> ProviderStream:
        """Start a streaming chat completion request to OpenRouter.

        Returns a lazy stream that connects on first iteration. The SDK
        handles SSE parsing and typed chunk deserialization internally.
        """
        return _OpenRouterStream(
            client=self._client,
            model=model,
            messages=messages,
            timeout_seconds=timeout_seconds,
        )


class _OpenRouterStream:
    """Async iterator over streaming chunks from OpenRouter via the OpenAI SDK.

    Lazily connects on first iteration (``stream()`` is sync per Protocol).
    The SDK handles SSE parsing, connection lifecycle, and typed chunk
    deserialization internally — no manual ``data:`` line parsing needed.
    """

    def __init__(
        self,
        *,
        client: openai.AsyncOpenAI,
        model: str,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> None:
        self._client = client
        self._model = model
        self._messages = messages
        self._timeout_seconds = timeout_seconds
        self._inner: AsyncStream[ChatCompletionChunk] | None = None
        self._usage_snapshot: UsageSnapshot | None = None
        self._delta_index = 0

    def __aiter__(self) -> AsyncIterator[StreamDelta]:
        """Return self as the async iterator."""
        return self

    async def _connect(
        self,
    ) -> AsyncStream[ChatCompletionChunk]:
        """Open the streaming connection to OpenRouter."""
        sdk_messages = cast(list[ChatCompletionMessageParam], self._messages)
        try:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=sdk_messages,
                stream=True,
                # Request usage data in the final streaming chunk so we can
                # report token counts without a separate API call.
                stream_options={"include_usage": True},
                timeout=self._timeout_seconds,
            )
        except openai.APIError as exc:
            raise _translate_error(exc) from exc

    async def __anext__(self) -> StreamDelta:
        """Return the next content delta, connecting lazily on first call."""
        if self._inner is None:
            self._inner = await self._connect()

        try:
            while True:
                chunk = await self._inner.__anext__()

                # Extract usage from the final chunk if present.
                # The SDK includes a CompletionUsage object on the last chunk
                # when stream_options.include_usage is True.
                if chunk.usage is not None:
                    self._usage_snapshot = _extract_usage(chunk.usage)

                # Skip chunks without content (role announcements, usage-only, etc.)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content is None or delta.content == "":
                    continue

                result = StreamDelta(text=delta.content, delta_index=self._delta_index)
                self._delta_index += 1
                return result
        except StopAsyncIteration:
            raise
        except openai.APIError as exc:
            raise _translate_error(exc) from exc

    async def usage(self) -> UsageSnapshot | None:
        """Return usage data extracted from the stream after consumption."""
        return self._usage_snapshot
