"""Fake provider tests — deterministic responses and failure simulation."""

import pytest

from nelson.core.errors import (
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderTransportError,
    StructuredOutputInvalidError,
)
from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import FinishReason
from nelson.providers.base import ProviderResponse, StreamDelta
from nelson.providers.fake import FakeProvider


async def test_fake_returns_structured_output() -> None:
    """Configure fake with a valid response, invoke, assert parsed result matches."""
    expected_parsed: dict[str, object] = {"task_type": "factual", "objective": "test objective"}
    response = ProviderResponse(
        content='{"task_type": "factual", "objective": "test objective"}',
        parsed=expected_parsed,
        finish_reason=FinishReason.STOP,
    )
    provider = FakeProvider(responses=[response])

    result = await provider.invoke(
        model="test/model",
        messages=[{"role": "user", "content": "test"}],
    )
    assert result.parsed == expected_parsed
    assert result.content == response.content
    assert result.finish_reason == FinishReason.STOP


async def test_fake_streams_deltas() -> None:
    """Configure fake with delta sequence, stream, assert deltas arrive in order."""
    deltas = [
        StreamDelta(text="Hello", delta_index=0),
        StreamDelta(text=" world", delta_index=1),
        StreamDelta(text="!", delta_index=2),
    ]
    provider = FakeProvider(stream_deltas=[deltas])

    collected: list[StreamDelta] = []
    stream = provider.stream(
        model="test/model",
        messages=[{"role": "user", "content": "test"}],
    )
    async for delta in stream:
        collected.append(delta)

    assert len(collected) == 3
    assert [d.text for d in collected] == ["Hello", " world", "!"]
    assert [d.delta_index for d in collected] == [0, 1, 2]

    # Usage should be available after streaming completes
    usage = await stream.usage()
    # Default fake stream has no usage unless configured
    assert usage is None or isinstance(usage, UsageSnapshot)


async def test_fake_simulates_timeout() -> None:
    """Configure fake to timeout, invoke, assert ProviderTimeoutError."""
    provider = FakeProvider(error=ProviderTimeoutError("Timed out after 60s"))

    with pytest.raises(ProviderTimeoutError, match="Timed out"):
        await provider.invoke(
            model="test/model",
            messages=[{"role": "user", "content": "test"}],
        )


async def test_fake_simulates_invalid_json() -> None:
    """Configure fake to return bad JSON, invoke, assert StructuredOutputInvalidError."""
    provider = FakeProvider(error=StructuredOutputInvalidError("Invalid JSON response"))

    with pytest.raises(StructuredOutputInvalidError, match="Invalid JSON"):
        await provider.invoke(
            model="test/model",
            messages=[{"role": "user", "content": "test"}],
        )


async def test_fake_simulates_transport_failure() -> None:
    """Configure fake to fail, invoke, assert ProviderTransportError."""
    provider = FakeProvider(error=ProviderTransportError("Connection refused"))

    with pytest.raises(ProviderTransportError, match="Connection refused"):
        await provider.invoke(
            model="test/model",
            messages=[{"role": "user", "content": "test"}],
        )


async def test_fake_simulates_auth_failure() -> None:
    """Configure fake to reject auth, invoke, assert ProviderAuthError."""
    provider = FakeProvider(error=ProviderAuthError("Invalid API key"))

    with pytest.raises(ProviderAuthError, match="Invalid API key"):
        await provider.invoke(
            model="test/model",
            messages=[{"role": "user", "content": "test"}],
        )


async def test_fake_error_propagates_during_streaming() -> None:
    """Configured error raises on first iteration of stream, not just invoke."""
    provider = FakeProvider(error=ProviderTransportError("stream failed"))

    stream = provider.stream(
        model="test/model",
        messages=[{"role": "user", "content": "test"}],
    )
    with pytest.raises(ProviderTransportError, match="stream failed"):
        async for _delta in stream:
            pass


async def test_fake_returns_usage() -> None:
    """Configure fake with usage data, invoke, assert usage snapshot populated."""
    usage = UsageSnapshot(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.003,
    )
    response = ProviderResponse(
        content="test response",
        finish_reason=FinishReason.STOP,
        usage=usage,
    )
    provider = FakeProvider(responses=[response])

    result = await provider.invoke(
        model="test/model",
        messages=[{"role": "user", "content": "test"}],
    )
    assert result.usage is not None
    assert result.usage.prompt_tokens == 100
    assert result.usage.completion_tokens == 50
    assert result.usage.total_tokens == 150
    assert result.usage.cost_usd == 0.003
