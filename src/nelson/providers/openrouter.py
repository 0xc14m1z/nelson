"""OpenRouter provider — real API calls via httpx.

Implements the ``Provider`` protocol for OpenRouter's chat completions
API. Supports both non-streaming and SSE streaming modes, with usage
extraction from the response.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from typing import cast

import httpx

from nelson.core.errors import (
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import FinishReason
from nelson.providers.base import ProviderResponse, ProviderStream, StreamDelta

# OpenRouter chat completions endpoint
_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def _auth_headers(api_key: str) -> dict[str, str]:
    """Build the standard Authorization + Content-Type headers."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_usage(data: dict[str, object]) -> UsageSnapshot | None:
    """Extract a UsageSnapshot from an OpenRouter response payload.

    Returns None if the response does not include usage data.

    Response schema reference:
    https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request
    """
    usage_raw = data.get("usage")
    if not isinstance(usage_raw, dict):
        return None
    # Cast to typed dict — isinstance confirms it's a dict, but pyright
    # infers unknown value types from the outer dict[str, object].
    usage = cast(dict[str, object], usage_raw)
    # Coerce to int | None — OpenRouter sends ints, but json.loads
    # returns them inside an untyped dict.
    raw_prompt = usage.get("prompt_tokens")
    raw_completion = usage.get("completion_tokens")
    raw_total = usage.get("total_tokens")
    return UsageSnapshot(
        prompt_tokens=int(raw_prompt) if isinstance(raw_prompt, (int, float)) else None,
        completion_tokens=int(raw_completion) if isinstance(raw_completion, (int, float)) else None,
        total_tokens=int(raw_total) if isinstance(raw_total, (int, float)) else None,
    )


class OpenRouterStream:
    """Async iterator over SSE deltas from an OpenRouter streaming response.

    Parses Server-Sent Events from the httpx response and yields
    ``StreamDelta`` objects for each content-bearing chunk. Usage is
    extracted from the final ``[DONE]``-adjacent frame if available.
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._lines = response.aiter_lines()
        self._usage_snapshot: UsageSnapshot | None = None
        self._delta_index = 0
        self._done = False

    def __aiter__(self) -> AsyncIterator[StreamDelta]:
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> StreamDelta:
        """Parse the next SSE event and return a StreamDelta.

        Skips keepalive frames and non-content events. Extracts usage
        from the final data frame before [DONE].
        """
        while True:
            if self._done:
                raise StopAsyncIteration
            try:
                line = await self._lines.__anext__()
            except StopAsyncIteration:
                self._done = True
                raise

            # SSE lines are prefixed with "data: "
            if not line.startswith("data: "):
                continue

            payload = line[6:]  # strip "data: " prefix

            # [DONE] signals end of stream
            if payload.strip() == "[DONE]":
                self._done = True
                raise StopAsyncIteration

            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                # Skip malformed frames (keepalive, comments)
                continue

            # Extract usage if present (usually on the final frame)
            frame_usage = _extract_usage(data)
            if frame_usage is not None:
                self._usage_snapshot = frame_usage

            # Extract content delta from the parsed JSON structure.
            # The JSON is untyped (dict[str, object]) so we use cast()
            # after isinstance guards to satisfy pyright.
            choices_raw = data.get("choices", [])
            if not choices_raw or not isinstance(choices_raw, list):
                continue
            choices = cast(list[object], choices_raw)
            first_choice_raw = choices[0]
            if not isinstance(first_choice_raw, dict):
                continue
            first_choice = cast(dict[str, object], first_choice_raw)
            delta_raw = first_choice.get("delta", {})
            if not isinstance(delta_raw, dict):
                continue
            delta_dict = cast(dict[str, object], delta_raw)
            content_val = delta_dict.get("content")
            if not isinstance(content_val, str) or content_val == "":
                # Skip non-content deltas (role announcements, None, etc.)
                continue

            result = StreamDelta(text=content_val, delta_index=self._delta_index)
            self._delta_index += 1
            return result

    async def usage(self) -> UsageSnapshot | None:
        """Return usage data extracted from the stream.

        Should be called after the stream is fully consumed.
        """
        return self._usage_snapshot


class OpenRouterProvider:
    """Provider implementation for OpenRouter's chat completions API.

    Uses httpx for async HTTP. Translates transport errors into
    domain-specific exception types.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def invoke(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object] | None = None,
        timeout_seconds: float = 60.0,
    ) -> ProviderResponse:
        """Send a non-streaming chat completion request to OpenRouter."""
        body: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if response_schema is not None:
            # TODO(phase-6): OpenRouter expects json_schema to contain
            # {"name": "...", "strict": true, "schema": {...}}, not a bare
            # schema. The caller contract needs a design decision when the
            # consensus engine starts using structured output.
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": response_schema,
            }

        headers = _auth_headers(self._api_key)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    _COMPLETIONS_URL,
                    json=body,
                    headers=headers,
                    timeout=timeout_seconds,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"OpenRouter request timed out after {timeout_seconds}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportError(f"OpenRouter request failed: {exc}") from exc

        # Check for auth errors before parsing response body
        if resp.status_code in (401, 403):
            raise ProviderAuthError(f"OpenRouter rejected the API key (HTTP {resp.status_code})")
        # Other error status codes are transport failures
        if resp.status_code >= 400:
            raise ProviderTransportError(
                f"OpenRouter returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        choices = data.get("choices", [])
        content = ""
        finish_reason = FinishReason.STOP
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            # Coerce the API string into the enum — unknown values fall back
            # to STOP so callers always get a valid FinishReason.
            raw_reason = choices[0].get("finish_reason", "stop")
            try:
                finish_reason = FinishReason(raw_reason)
            except ValueError:
                finish_reason = FinishReason.STOP

        usage = _extract_usage(data)

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

        Returns an ``OpenRouterStream`` that yields deltas as they arrive.
        The stream must be consumed within an async context. Usage data
        is available via ``await stream.usage()`` after consumption.
        """
        # Return a lazy stream that connects on first iteration
        return _LazyOpenRouterStream(
            api_key=self._api_key,
            model=model,
            messages=messages,
            timeout_seconds=timeout_seconds,
        )


class _LazyOpenRouterStream:
    """Stream that lazily opens the SSE connection on first iteration.

    This allows ``provider.stream()`` to be a sync method (as required
    by the Provider Protocol) while still using async httpx internally.

    NOTE: ``_cleanup()`` is only called on natural stream exhaustion.
    If the consumer abandons the stream early (breaks out of the loop),
    httpx resources will leak. The consensus engine (Phase 6) must
    handle early-exit cleanup by calling ``aclose()`` on the response.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._messages = messages
        self._timeout_seconds = timeout_seconds
        self._inner: OpenRouterStream | None = None
        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None

    def __aiter__(self) -> AsyncIterator[StreamDelta]:
        """Return self as the async iterator."""
        return self

    async def _connect(self) -> OpenRouterStream:
        """Open the SSE connection and return the inner stream."""
        body: dict[str, object] = {
            "model": self._model,
            "messages": self._messages,
            "stream": True,
        }
        headers = _auth_headers(self._api_key)

        # Pass timeout to the client — httpx.AsyncClient.send() does not
        # accept a timeout parameter directly.
        self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            # Use a local variable so pyright can narrow the type —
            # instance attributes typed as T | None cannot be narrowed.
            response = await self._client.send(
                self._client.build_request(
                    "POST",
                    _COMPLETIONS_URL,
                    json=body,
                    headers=headers,
                ),
                stream=True,
            )
        except httpx.TimeoutException as exc:
            await self._client.aclose()
            raise ProviderTimeoutError(
                f"OpenRouter stream timed out after {self._timeout_seconds}s"
            ) from exc
        except httpx.HTTPError as exc:
            await self._client.aclose()
            raise ProviderTransportError(f"OpenRouter stream failed: {exc}") from exc

        if response.status_code in (401, 403):
            await response.aclose()
            await self._client.aclose()
            raise ProviderAuthError(
                f"OpenRouter rejected the API key (HTTP {response.status_code})"
            )
        if response.status_code >= 400:
            # Read the body for error details before closing
            body_text = ""
            async for chunk in response.aiter_text():
                body_text += chunk
                if len(body_text) > 200:
                    break
            await response.aclose()
            await self._client.aclose()
            raise ProviderTransportError(
                f"OpenRouter returned HTTP {response.status_code}: {body_text[:200]}"
            )

        self._response = response
        return OpenRouterStream(response)

    async def __anext__(self) -> StreamDelta:
        """Return the next delta, connecting lazily on first call."""
        if self._inner is None:
            self._inner = await self._connect()
        try:
            return await self._inner.__anext__()
        except StopAsyncIteration:
            # Clean up httpx resources when the stream ends
            await self._cleanup()
            raise
        except httpx.TimeoutException as exc:
            # Read timeout during streaming — map to domain error and clean up
            await self._cleanup()
            raise ProviderTimeoutError(
                f"OpenRouter stream read timed out after {self._timeout_seconds}s"
            ) from exc
        except httpx.HTTPError as exc:
            # Network failure during streaming — map to domain error and clean up
            await self._cleanup()
            raise ProviderTransportError(f"OpenRouter stream read failed: {exc}") from exc

    async def _cleanup(self) -> None:
        """Close the httpx response and client."""
        if self._response is not None:
            await self._response.aclose()
        if self._client is not None:
            await self._client.aclose()

    async def usage(self) -> UsageSnapshot | None:
        """Return usage data from the inner stream after consumption."""
        if self._inner is not None:
            return await self._inner.usage()
        return None
