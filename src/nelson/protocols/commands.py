"""Typed application command models."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from nelson.protocols.enums import Adapter, CommandType, InputSource, ReleaseGateMode


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def _make_command_id() -> str:
    """Generate a unique command identifier with ``cmd_`` prefix."""
    return f"cmd_{uuid.uuid4().hex[:12]}"


class AuthSetCommand(BaseModel):
    """Command to save an OpenRouter API key."""

    command_id: str = Field(
        default_factory=_make_command_id, description="Unique identifier for this command."
    )
    type: CommandType = Field(default=CommandType.AUTH_SET, description="Command discriminator.")
    issued_at: datetime = Field(
        default_factory=_utc_now, description="When the command was issued."
    )
    adapter: Adapter = Field(
        default=Adapter.CLI, description="Interface that originated the command."
    )
    api_key: str = Field(description="OpenRouter API key to save.")

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, v: str) -> str:
        """Reject empty or whitespace-only keys (CLI_SPEC §5.1)."""
        if not v.strip():
            raise ValueError("API key must not be empty")
        return v


class AuthStatusCommand(BaseModel):
    """Command to check credential status."""

    command_id: str = Field(
        default_factory=_make_command_id, description="Unique identifier for this command."
    )
    type: CommandType = Field(default=CommandType.AUTH_STATUS, description="Command discriminator.")
    issued_at: datetime = Field(
        default_factory=_utc_now, description="When the command was issued."
    )
    adapter: Adapter = Field(
        default=Adapter.CLI, description="Interface that originated the command."
    )


class AuthClearCommand(BaseModel):
    """Command to remove the saved API key."""

    command_id: str = Field(
        default_factory=_make_command_id, description="Unique identifier for this command."
    )
    type: CommandType = Field(default=CommandType.AUTH_CLEAR, description="Command discriminator.")
    issued_at: datetime = Field(
        default_factory=_utc_now, description="When the command was issued."
    )
    adapter: Adapter = Field(
        default=Adapter.CLI, description="Interface that originated the command."
    )


class RunCommand(BaseModel):
    """Command to start a multi-LLM consensus session."""

    command_id: str = Field(
        default_factory=_make_command_id, description="Unique identifier for this command."
    )
    type: CommandType = Field(default=CommandType.RUN, description="Command discriminator.")
    issued_at: datetime = Field(
        default_factory=_utc_now, description="When the command was issued."
    )
    adapter: Adapter = Field(
        default=Adapter.CLI, description="Interface that originated the command."
    )
    input_source: InputSource = Field(description="How the prompt was provided.")
    prompt_text: str = Field(description="The user's prompt text.")
    participants: list[str] = Field(description="OpenRouter model IDs for participants.")
    moderator: str = Field(description="OpenRouter model ID for the moderator.")
    max_rounds: int = Field(default=10, description="Maximum number of consensus rounds.")
    release_gate_mode: ReleaseGateMode = Field(
        default=ReleaseGateMode.AUTO, description="Release gate mode."
    )
    openrouter_api_key_override: str | None = Field(
        default=None, description="One-time API key override (not persisted)."
    )


ApplicationCommand = AuthSetCommand | AuthStatusCommand | AuthClearCommand | RunCommand
"""Union of all typed application commands."""
