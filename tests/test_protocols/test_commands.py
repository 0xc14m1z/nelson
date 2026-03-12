"""Command model validation tests (T-PROTO-001)."""

import json

from nelson.protocols.commands import (
    AuthClearCommand,
    AuthSetCommand,
    AuthStatusCommand,
    RunCommand,
)
from nelson.protocols.enums import InputSource, ReleaseGateMode


def test_auth_set_command_validates() -> None:
    cmd = AuthSetCommand(
        command_id="cmd_001",
        api_key="sk-or-test-key",
    )
    data = json.loads(cmd.model_dump_json())
    assert data["type"] == "auth_set"
    assert data["command_id"] == "cmd_001"
    assert data["api_key"] == "sk-or-test-key"
    assert "issued_at" in data
    assert data["adapter"] == "cli"


def test_auth_status_command_validates() -> None:
    cmd = AuthStatusCommand(command_id="cmd_002")
    data = json.loads(cmd.model_dump_json())
    assert data["type"] == "auth_status"
    assert data["command_id"] == "cmd_002"
    assert "issued_at" in data


def test_auth_clear_command_validates() -> None:
    cmd = AuthClearCommand(command_id="cmd_003")
    data = json.loads(cmd.model_dump_json())
    assert data["type"] == "auth_clear"
    assert data["command_id"] == "cmd_003"


def test_run_command_validates() -> None:
    cmd = RunCommand(
        command_id="cmd_004",
        input_source=InputSource.PROMPT,
        prompt_text="What is Python?",
        participants=["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
        moderator="openai/gpt-4.1",
        max_rounds=10,
        release_gate_mode=ReleaseGateMode.AUTO,
    )
    data = json.loads(cmd.model_dump_json())
    assert data["type"] == "run"
    assert data["command_id"] == "cmd_004"
    assert data["input_source"] == "prompt"
    assert data["prompt_text"] == "What is Python?"
    assert len(data["participants"]) == 2
    assert data["moderator"] == "openai/gpt-4.1"
    assert data["max_rounds"] == 10
    assert data["release_gate_mode"] == "auto"
    assert data["openrouter_api_key_override"] is None
