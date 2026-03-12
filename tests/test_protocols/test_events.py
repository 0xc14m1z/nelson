"""Event model validation tests (T-EVENT-001, T-EVENT-004)."""

import json

import pytest

from nelson.protocols.enums import EventType, Phase, Role
from nelson.protocols.events import PAYLOAD_MAP, ApplicationEvent

EVENT_EXAMPLES: list[dict[str, object]] = [
    {
        "type": "command_received",
        "phase": "command",
        "role": "system",
        "payload": {"command_type": "run", "adapter": "cli"},
    },
    {
        "type": "command_completed",
        "phase": "command",
        "role": "system",
        "payload": {"command_type": "run", "status": "success"},
    },
    {
        "type": "command_failed",
        "phase": "command",
        "role": "system",
        "payload": {
            "command_type": "run",
            "error": {
                "code": "participant_quorum_lost",
                "message": "Only one valid participant remained",
                "retryable": False,
                "details": {},
            },
        },
    },
    {
        "type": "auth_key_saved",
        "phase": "auth",
        "role": "system",
        "payload": {"storage_path": "~/.nelson/openrouter_api_key"},
    },
    {
        "type": "auth_status_reported",
        "phase": "auth",
        "role": "system",
        "payload": {
            "saved_key_present": True,
            "env_key_present": False,
            "effective_source": "saved",
            "verification": "valid",
        },
    },
    {
        "type": "auth_key_cleared",
        "phase": "auth",
        "role": "system",
        "payload": {"saved_key_removed": True},
    },
    {
        "type": "run_started",
        "phase": "startup",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "input_source": "prompt",
            "max_rounds": 10,
            "release_gate_mode": "auto",
            "participants": ["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
            "moderator": "openai/gpt-4.1",
        },
    },
    {
        "type": "run_completed",
        "phase": "finalization",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "status": "success",
            "rounds_completed": 2,
            "consensus_status": "reached",
            "framing_version": 1,
            "final_answer_chars": 1248,
            "duration_ms": 18342,
        },
    },
    {
        "type": "run_failed",
        "phase": "error",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "status": "failed",
            "framing_version": 1,
            "error": {
                "code": "moderator_failed",
                "message": "Moderator could not complete",
                "retryable": False,
                "details": {},
            },
        },
    },
    {
        "type": "progress_updated",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "round": 2,
        "payload": {
            "phase_name": "participant_review",
            "phase_index": 5,
            "phase_count_estimate": 7,
            "round": 2,
            "max_rounds": 10,
            "completed_units": 1,
            "total_units": 3,
            "stage_progress": 0.33,
            "overall_progress_estimate": 0.34,
            "is_estimate": True,
            "message": "Reviewing moderator candidate",
        },
    },
    {
        "type": "consensus_pending",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "candidate_id": "cand_02",
            "reviewer_count": 2,
            "blocking_review_count": 1,
            "minor_revise_count": 1,
            "major_revise_count": 1,
            "reject_count": 0,
            "summary": "One blocking issue remains",
        },
    },
    {
        "type": "consensus_reached",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "candidate_id": "cand_03",
            "reviewer_count": 3,
            "approve_count": 2,
            "minor_revise_count": 1,
            "major_revise_count": 0,
            "reject_count": 0,
            "summary": "No blocking objections remain",
        },
    },
    {
        "type": "consensus_partial",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "candidate_id": "cand_05",
            "reason": "max_rounds_exhausted",
            "unresolved_issues": ["One participant believes the answer should include caveats"],
        },
    },
    {
        "type": "task_framing_started",
        "phase": "task_framing",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "payload": {
            "invocation_id": "inv_001",
            "schema_name": "TaskFraming",
            "streaming": True,
        },
    },
    {
        "type": "task_framing_completed",
        "phase": "task_framing",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "payload": {
            "invocation_id": "inv_001",
            "task_type": "analytical",
            "sensitivity": "low",
            "objective": "Provide a complete and accurate answer",
            "quality_criteria": ["accuracy", "coverage", "clarity"],
            "aspects_to_cover": ["architecture", "testing"],
            "ambiguities": [],
            "assumptions": [],
            "framing_version": 1,
        },
    },
    {
        "type": "task_framing_updated",
        "phase": "task_framing",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 2,
        "payload": {
            "task_type": "analytical",
            "sensitivity": "medium",
            "objective": "Provide a complete and accurate answer",
            "quality_criteria": ["accuracy", "coverage", "clarity"],
            "aspects_to_cover": ["architecture", "testing", "deployment caveats"],
            "ambiguities": [],
            "assumptions": [],
            "framing_version": 2,
            "previous_framing_version": 1,
            "effective_from_round": 3,
            "invalidated_candidate_id": "cand_02",
            "update_reason": "A material framing issue was identified",
        },
    },
    {
        "type": "model_started",
        "phase": "participant_generation",
        "role": "participant",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "invocation_id": "inv_002",
            "purpose": "initial_contribution",
            "framing_version": 1,
            "schema_name": "ParticipantInitialContribution",
            "streaming": True,
            "retry_index": 0,
        },
    },
    {
        "type": "model_delta",
        "phase": "participant_generation",
        "role": "participant",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "invocation_id": "inv_002",
            "delta_index": 12,
            "text": "Testing is not optional...",
            "is_structured_output": False,
        },
    },
    {
        "type": "model_completed",
        "phase": "participant_generation",
        "role": "participant",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "invocation_id": "inv_002",
            "purpose": "initial_contribution",
            "framing_version": 1,
            "finish_reason": "stop",
            "output_format": "structured",
            "parsed": {"answer_markdown": "..."},
        },
    },
    {
        "type": "model_failed",
        "phase": "participant_review",
        "role": "participant",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "invocation_id": "inv_002",
            "purpose": "candidate_review",
            "framing_version": 1,
            "retry_index": 1,
            "error": {
                "code": "structured_output_invalid",
                "message": "Model output did not validate",
                "retryable": False,
                "details": {},
            },
        },
    },
    {
        "type": "participant_excluded",
        "phase": "participant_generation",
        "role": "participant",
        "model": "anthropic/claude-3.7-sonnet",
        "run_id": "run_001",
        "payload": {
            "reason_code": "structured_output_repair_failed",
            "reason_summary": (
                "Participant excluded after invalid structured output and failed repair"
            ),
            "failed_invocation_id": "inv_014",
            "remaining_active_participant_count": 2,
            "quorum_preserved": True,
        },
    },
    {
        "type": "round_started",
        "phase": "participant_generation",
        "role": "system",
        "run_id": "run_001",
        "round": 2,
        "payload": {
            "round": 2,
            "candidate_id": "cand_02",
            "framing_version": 1,
            "target_participant_count": 3,
        },
    },
    {
        "type": "round_completed",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "round": 2,
        "payload": {
            "round": 2,
            "candidate_id": "cand_02",
            "framing_version": 1,
            "review_executed": True,
            "approve_count": 1,
            "minor_revise_count": 1,
            "major_revise_count": 1,
            "reject_count": 0,
            "candidate_invalidated_by_framing_update": False,
            "will_continue": True,
        },
    },
    {
        "type": "candidate_created",
        "phase": "candidate_synthesis",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "candidate_id": "cand_01",
            "framing_version": 1,
            "source": "initial_synthesis",
            "text": "Here is the synthesized answer...",
            "summary": "Initial moderator synthesis",
            "excerpt_count": 3,
        },
    },
    {
        "type": "candidate_updated",
        "phase": "candidate_synthesis",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "round": 2,
        "payload": {
            "candidate_id": "cand_02",
            "previous_candidate_id": "cand_01",
            "framing_version": 1,
            "source": "major_revise_cycle",
            "text": "Updated candidate answer...",
            "summary": "Added stronger caveats",
        },
    },
    {
        "type": "review_started",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "candidate_id": "cand_02",
            "framing_version": 1,
            "target_participant_count": 3,
        },
    },
    {
        "type": "review_completed",
        "phase": "participant_review",
        "role": "system",
        "run_id": "run_001",
        "round": 1,
        "payload": {
            "candidate_id": "cand_02",
            "framing_version": 1,
            "reviewer_count": 3,
            "approve_count": 1,
            "minor_revise_count": 1,
            "major_revise_count": 1,
            "reject_count": 0,
            "blocking_issue_summaries": ["One participant flagged an unsupported claim"],
            "minor_improvement_summaries": ["Clarify packaging recommendation"],
        },
    },
    {
        "type": "release_gate_started",
        "phase": "release_gate",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "payload": {
            "invocation_id": "inv_010",
            "mode": "auto",
            "candidate_id": "cand_03",
            "framing_version": 1,
        },
    },
    {
        "type": "release_gate_completed",
        "phase": "release_gate",
        "role": "moderator",
        "model": "openai/gpt-4.1",
        "run_id": "run_001",
        "payload": {
            "invocation_id": "inv_010",
            "candidate_id": "cand_03",
            "framing_version": 1,
            "executed": True,
            "decision": "pass_with_minor_fixes",
            "summary": "Added a caveat about context dependence",
            "minor_fixes_applied": ["Added caveat about deployment context"],
            "blocking_issues": [],
        },
    },
    {
        "type": "usage_reported",
        "phase": "finalization",
        "role": "system",
        "run_id": "run_001",
        "payload": {
            "scope": "invocation",
            "invocation_id": "inv_002",
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 450,
                "total_tokens": 1650,
                "cost_usd": None,
                "currency": "USD",
                "is_normalized": True,
                "is_complete": True,
            },
        },
    },
]


@pytest.mark.parametrize(
    "example",
    EVENT_EXAMPLES,
    ids=[str(e["type"]) for e in EVENT_EXAMPLES],
)
def test_every_event_type_validates(example: dict[str, object]) -> None:
    """Every event type must be constructable and serializable."""
    envelope_data = {
        "event_id": "evt_test",
        "command_id": "cmd_test",
        "run_id": example.get("run_id"),
        "sequence": 1,
        "timestamp": "2026-03-09T12:34:56.789Z",
        "type": example["type"],
        "phase": example["phase"],
        "round": example.get("round"),
        "role": example["role"],
        "model": example.get("model"),
        "payload": example["payload"],
    }
    event = ApplicationEvent.model_validate(envelope_data)
    dumped = json.loads(event.model_dump_json())
    assert dumped["type"] == example["type"]
    assert dumped["phase"] == example["phase"]


def test_payload_map_covers_all_event_types() -> None:
    """Every EventType must have a corresponding entry in PAYLOAD_MAP."""
    for event_type in EventType:
        assert event_type.value in PAYLOAD_MAP, f"{event_type.value} missing from PAYLOAD_MAP"


def test_event_schema_export() -> None:
    """JSON Schema export must contain all event types."""
    schema = ApplicationEvent.model_json_schema()
    schema_str = json.dumps(schema)
    for event_type in EventType:
        assert event_type.value in schema_str, f"{event_type.value} missing from schema"


def test_command_received_example() -> None:
    """Validate the canonical command_received payload from EVENT_SCHEMA.md §4.0."""
    event = ApplicationEvent.model_validate(
        {
            "event_id": "evt_001",
            "command_id": "cmd_001",
            "run_id": None,
            "sequence": 1,
            "timestamp": "2026-03-09T12:34:56.789Z",
            "type": "command_received",
            "phase": "command",
            "round": None,
            "role": "system",
            "model": None,
            "payload": {"command_type": "run", "adapter": "cli"},
        }
    )
    assert event.type == EventType.COMMAND_RECEIVED
    assert event.phase == Phase.COMMAND
    assert event.role == Role.SYSTEM


def test_run_started_example() -> None:
    """Validate the canonical run_started payload from EVENT_SCHEMA.md §4.1."""
    event = ApplicationEvent.model_validate(
        {
            "event_id": "evt_002",
            "command_id": "cmd_001",
            "run_id": "run_001",
            "sequence": 2,
            "timestamp": "2026-03-09T12:34:56.789Z",
            "type": "run_started",
            "phase": "startup",
            "round": None,
            "role": "system",
            "model": None,
            "payload": {
                "input_source": "prompt",
                "max_rounds": 10,
                "release_gate_mode": "auto",
                "participants": ["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
                "moderator": "openai/gpt-4.1",
            },
        }
    )
    assert event.type == EventType.RUN_STARTED
    assert event.phase == Phase.STARTUP
