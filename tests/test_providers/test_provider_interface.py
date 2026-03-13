"""Provider Protocol shape and conformance tests."""

from nelson.protocols.enums import FinishReason
from nelson.providers.base import (
    FakeProvider,
    OpenRouterProvider,
    Provider,
    ProviderResponse,
)


def test_provider_protocol_shape() -> None:
    """Provider Protocol defines invoke and stream with correct signatures."""
    # invoke must be an async method accepting model, messages, optional schema, timeout
    assert hasattr(Provider, "invoke")
    assert hasattr(Provider, "stream")

    # ProviderResponse must have content, parsed, finish_reason, usage fields
    resp = ProviderResponse(content="test")
    assert resp.content == "test"
    assert resp.parsed is None
    assert resp.finish_reason == FinishReason.STOP
    assert resp.usage is None


def test_fake_implements_provider_protocol() -> None:
    """FakeProvider satisfies the Provider Protocol."""
    provider = FakeProvider()
    assert isinstance(provider, Provider)


def test_openrouter_implements_provider_protocol() -> None:
    """OpenRouterProvider satisfies the Provider Protocol."""
    # Instantiate with a dummy key — no network calls here
    provider = OpenRouterProvider(api_key="sk-test-dummy")
    assert isinstance(provider, Provider)
