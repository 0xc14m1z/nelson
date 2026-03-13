"""OpenRouter provider live tests — real API calls.

These tests require a valid OPENROUTER_API_KEY environment variable.
They are marked with 'live' and excluded from the default test suite.
"""

import os

import pytest

from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import FinishReason
from nelson.providers.base import StreamDelta
from nelson.providers.openrouter import OpenRouterProvider

pytestmark = pytest.mark.live

# Use a cheap, fast model for live tests
LIVE_MODEL = "openai/gpt-4.1-mini"


@pytest.fixture
def provider() -> OpenRouterProvider:
    """Create an OpenRouterProvider with the env API key."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return OpenRouterProvider(api_key=api_key)


async def test_openrouter_non_streaming_call(provider: OpenRouterProvider) -> None:
    """One real non-streaming call, assert response has content."""
    result = await provider.invoke(
        model=LIVE_MODEL,
        messages=[{"role": "user", "content": "Say 'hello' and nothing else."}],
    )
    assert result.content
    assert len(result.content) > 0
    assert result.finish_reason == FinishReason.STOP


async def test_openrouter_streaming_call(provider: OpenRouterProvider) -> None:
    """One real streaming call, assert deltas arrive."""
    deltas: list[StreamDelta] = []
    stream = provider.stream(
        model=LIVE_MODEL,
        messages=[{"role": "user", "content": "Say 'hello' and nothing else."}],
    )
    async for delta in stream:
        deltas.append(delta)
    assert len(deltas) > 0
    full_text = "".join(d.text for d in deltas)
    assert len(full_text) > 0


async def test_openrouter_extracts_usage(provider: OpenRouterProvider) -> None:
    """Assert usage snapshot from real call."""
    result = await provider.invoke(
        model=LIVE_MODEL,
        messages=[{"role": "user", "content": "Say 'hello' and nothing else."}],
    )
    # Usage may or may not be present depending on model
    if result.usage is not None:
        assert isinstance(result.usage, UsageSnapshot)
        assert result.usage.total_tokens is None or result.usage.total_tokens > 0
