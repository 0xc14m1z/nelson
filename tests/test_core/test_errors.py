"""Domain error tests — existence and error code mapping."""

from nelson.core.errors import (
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderTransportError,
    StructuredOutputInvalidError,
)
from nelson.protocols.enums import ErrorCode


def test_domain_errors_exist() -> None:
    """All provider error types can be instantiated with a message."""
    timeout = ProviderTimeoutError("timeout")
    assert str(timeout) == "timeout"

    transport = ProviderTransportError("connection failed")
    assert str(transport) == "connection failed"

    auth = ProviderAuthError("unauthorized")
    assert str(auth) == "unauthorized"

    invalid = StructuredOutputInvalidError("bad json")
    assert str(invalid) == "bad json"


def test_errors_map_to_error_codes() -> None:
    """Each domain error type maps to the correct CLI_SPEC §10 symbolic code."""
    timeout = ProviderTimeoutError("t")
    assert timeout.error_code == ErrorCode.PROVIDER_TIMEOUT

    transport = ProviderTransportError("t")
    assert transport.error_code == ErrorCode.PROVIDER_TRANSPORT_ERROR

    auth = ProviderAuthError("a")
    assert auth.error_code == ErrorCode.PROVIDER_AUTH_ERROR

    invalid = StructuredOutputInvalidError("i")
    assert invalid.error_code == ErrorCode.STRUCTURED_OUTPUT_INVALID
