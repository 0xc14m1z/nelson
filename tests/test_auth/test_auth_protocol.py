"""Auth protocol tests — dispatcher event stream (T-PROTO-003 adapted)."""

from pathlib import Path

from nelson.core.dispatcher import AuthCommandExecution, dispatch
from nelson.protocols.commands import AuthClearCommand, AuthSetCommand, AuthStatusCommand
from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import AuthClearResult, AuthSetResult, AuthStatusResult


async def _collect_events(execution: AuthCommandExecution) -> list[ApplicationEvent]:
    """Drain all events from a CommandExecution."""
    events: list[ApplicationEvent] = []
    async for event in execution.events:
        events.append(event)
    return events


async def test_auth_set_emits_correct_events(tmp_home: Path) -> None:
    """AuthSetCommand event stream: command_received, auth_key_saved, command_completed."""
    cmd = AuthSetCommand(command_id="cmd_test_set", api_key="sk-test")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types[0] == "command_received"
    assert "auth_key_saved" in event_types
    assert event_types[-1] == "command_completed"
    assert isinstance(result, AuthSetResult)


async def test_auth_status_emits_correct_events(tmp_home: Path) -> None:
    """AuthStatusCommand: command_received, auth_status_reported, command_completed."""
    cmd = AuthStatusCommand(command_id="cmd_test_status")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types[0] == "command_received"
    assert "auth_status_reported" in event_types
    assert event_types[-1] in ("command_completed", "command_failed")
    assert isinstance(result, AuthStatusResult)


async def test_auth_clear_emits_correct_events(tmp_home: Path) -> None:
    """AuthClearCommand event stream: command_received, auth_key_cleared, command_completed."""
    cmd = AuthClearCommand(command_id="cmd_test_clear")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types[0] == "command_received"
    assert "auth_key_cleared" in event_types
    assert event_types[-1] == "command_completed"
    assert isinstance(result, AuthClearResult)


async def test_auth_set_resolves_typed_result(tmp_home: Path) -> None:
    """AuthSetCommand terminal result is a typed AuthSetResult."""
    cmd = AuthSetCommand(command_id="cmd_test_result", api_key="sk-test")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    async for _ in execution.events:
        pass
    result = await execution.result()

    assert isinstance(result, AuthSetResult)
    assert result.saved is True
    assert "openrouter_api_key" in result.storage_path
