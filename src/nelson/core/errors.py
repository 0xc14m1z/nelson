"""Domain exception types for provider and orchestration failures.

Each error type carries an ``error_code`` attribute that maps to the
symbolic error codes defined in CLI_SPEC §10. This allows the CLI
layer to translate domain errors into structured ``ErrorObject``
payloads without hardcoding the mapping.
"""

from nelson.protocols.enums import ErrorCode


class NelsonError(Exception):
    """Base class for all Nelson domain errors."""

    error_code: ErrorCode


class ProviderTimeoutError(NelsonError):
    """A provider call exceeded the configured timeout."""

    error_code = ErrorCode.PROVIDER_TIMEOUT


class ProviderTransportError(NelsonError):
    """A provider call failed due to a network or transport error."""

    error_code = ErrorCode.PROVIDER_TRANSPORT_ERROR


class ProviderAuthError(NelsonError):
    """A provider rejected the API key as invalid or unauthorized."""

    error_code = ErrorCode.PROVIDER_AUTH_ERROR


class StructuredOutputInvalidError(NelsonError):
    """A provider returned output that failed structured validation."""

    error_code = ErrorCode.STRUCTURED_OUTPUT_INVALID
