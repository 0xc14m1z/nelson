"""Typed application command models."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from nelson.protocols.enums import Adapter, CommandType, InputSource, ReleaseGateMode


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuthSetCommand(BaseModel):
    command_id: str
    type: CommandType = CommandType.AUTH_SET
    issued_at: datetime = Field(default_factory=_utc_now)
    adapter: Adapter = Adapter.CLI
    api_key: str


class AuthStatusCommand(BaseModel):
    command_id: str
    type: CommandType = CommandType.AUTH_STATUS
    issued_at: datetime = Field(default_factory=_utc_now)
    adapter: Adapter = Adapter.CLI


class AuthClearCommand(BaseModel):
    command_id: str
    type: CommandType = CommandType.AUTH_CLEAR
    issued_at: datetime = Field(default_factory=_utc_now)
    adapter: Adapter = Adapter.CLI


class RunCommand(BaseModel):
    command_id: str
    type: CommandType = CommandType.RUN
    issued_at: datetime = Field(default_factory=_utc_now)
    adapter: Adapter = Adapter.CLI
    input_source: InputSource
    prompt_text: str
    participants: list[str]
    moderator: str
    max_rounds: int = 10
    release_gate_mode: ReleaseGateMode = ReleaseGateMode.AUTO
    openrouter_api_key_override: str | None = None


ApplicationCommand = AuthSetCommand | AuthStatusCommand | AuthClearCommand | RunCommand
