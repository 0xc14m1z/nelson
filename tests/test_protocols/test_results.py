"""Result model validation tests."""

import json

from nelson.protocols.results import (
    AuthClearResult,
    AuthSetResult,
    AuthStatusResult,
    RunResult,
)


def test_run_result_success_example() -> None:
    """Validate the canonical success JSON from RUN_RESULT_SCHEMA.md §12."""
    data: dict[str, object] = {
        "run_id": "run_01HXYZ",
        "status": "success",
        "error": None,
        "input": {"source": "prompt", "prompt_chars": 73, "prompt_file": None},
        "models": {
            "participants": ["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
            "moderator": "openai/gpt-4.1",
            "excluded_participants": [],
        },
        "task_framing": {
            "task_type": "analytical",
            "sensitivity": "low",
            "objective": "Provide a complete and accurate answer to the user's request",
            "quality_criteria": ["accuracy", "coverage", "clarity"],
            "aspects_to_cover": ["architecture", "testing", "packaging"],
            "ambiguities": [],
            "assumptions": [],
            "framing_version": 1,
        },
        "consensus": {
            "status": "reached",
            "rounds_completed": 2,
            "max_rounds": 10,
            "minor_revisions_applied": ["Clarified packaging guidance"],
            "blocking_issues_resolved": ["Removed unsupported claim about deployment tooling"],
            "residual_disagreements": [],
        },
        "release_gate": {
            "mode": "auto",
            "executed": True,
            "decision": "pass_with_minor_fixes",
            "summary": "Added a caveat about context dependence",
            "minor_fixes_applied": ["Added caveat about deployment context"],
            "blocking_issues": [],
        },
        "final_answer": "A good Python application should emphasize clarity...",
        "usage": {
            "per_invocation": [],
            "total": {
                "prompt_tokens": 2400,
                "completion_tokens": 1100,
                "total_tokens": 3500,
                "cost_usd": None,
                "currency": "USD",
                "is_normalized": True,
                "is_complete": True,
            },
        },
        "timing": {
            "started_at": "2026-03-09T12:34:56.789Z",
            "completed_at": "2026-03-09T12:35:14.123Z",
            "duration_ms": 17334,
        },
    }
    result = RunResult.model_validate(data)
    dumped = json.loads(result.model_dump_json())
    assert dumped["status"] == "success"
    assert dumped["final_answer"] is not None
    assert dumped["error"] is None


def test_run_result_partial_example() -> None:
    """Validate the canonical partial JSON from RUN_RESULT_SCHEMA.md §13."""
    data: dict[str, object] = {
        "run_id": "run_01HXYZ",
        "status": "partial",
        "error": None,
        "input": {"source": "prompt", "prompt_chars": 91, "prompt_file": None},
        "models": {
            "participants": ["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
            "moderator": "openai/gpt-4.1",
            "excluded_participants": [],
        },
        "task_framing": {
            "task_type": "comparative",
            "sensitivity": "low",
            "objective": "Recommend and compare stadiums",
            "quality_criteria": ["accuracy", "clear justification"],
            "aspects_to_cover": ["fan experience", "historical significance"],
            "ambiguities": ["Best may be subjective"],
            "assumptions": [],
            "framing_version": 1,
        },
        "consensus": {
            "status": "partial",
            "rounds_completed": 10,
            "max_rounds": 10,
            "minor_revisions_applied": [],
            "blocking_issues_resolved": [],
            "residual_disagreements": [
                "One participant wanted stronger qualification around subjectivity"
            ],
        },
        "release_gate": {
            "mode": "auto",
            "executed": True,
            "decision": "pass",
            "summary": "Answer is deliverable despite residual disagreement",
            "minor_fixes_applied": [],
            "blocking_issues": [],
        },
        "final_answer": "The best baseball stadiums in Finland...",
        "usage": {
            "per_invocation": [],
            "total": {
                "prompt_tokens": 4100,
                "completion_tokens": 2200,
                "total_tokens": 6300,
                "cost_usd": None,
                "currency": "USD",
                "is_normalized": True,
                "is_complete": True,
            },
        },
        "timing": {
            "started_at": "2026-03-09T12:34:56.789Z",
            "completed_at": "2026-03-09T12:36:21.123Z",
            "duration_ms": 84334,
        },
    }
    result = RunResult.model_validate(data)
    assert result.status == "partial"
    assert result.consensus.status == "partial"
    assert len(result.consensus.residual_disagreements) == 1


def test_run_result_failure_example() -> None:
    """Validate the canonical failure JSON from RUN_RESULT_SCHEMA.md §14."""
    data: dict[str, object] = {
        "run_id": "run_01HXYZ",
        "status": "failed",
        "error": {
            "code": "participant_quorum_lost",
            "message": "Only one valid participant remained after retries",
            "phase": "participant_review",
            "retryable": False,
            "details": {},
        },
        "input": {"source": "prompt", "prompt_chars": 91, "prompt_file": None},
        "models": {
            "participants": ["openai/gpt-4.1", "anthropic/claude-3.7-sonnet"],
            "moderator": "openai/gpt-4.1",
            "excluded_participants": [
                {
                    "model": "anthropic/claude-3.7-sonnet",
                    "round_excluded": 1,
                    "reason_code": "structured_output_repair_failed",
                    "reason_summary": (
                        "Participant excluded after invalid structured output and failed repair"
                    ),
                    "failed_invocation_id": "inv_008",
                }
            ],
        },
        "task_framing": {
            "task_type": "comparative",
            "sensitivity": "low",
            "objective": "Recommend and compare stadiums",
            "quality_criteria": ["accuracy"],
            "aspects_to_cover": ["spectator experience"],
            "ambiguities": [],
            "assumptions": [],
            "framing_version": 1,
        },
        "consensus": {
            "status": "failed",
            "rounds_completed": 1,
            "max_rounds": 10,
            "minor_revisions_applied": [],
            "blocking_issues_resolved": [],
            "residual_disagreements": [],
        },
        "release_gate": {
            "mode": "auto",
            "executed": False,
            "decision": "skipped",
            "summary": "Run failed before release gate",
            "minor_fixes_applied": [],
            "blocking_issues": [],
        },
        "final_answer": None,
        "usage": {
            "per_invocation": [],
            "total": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": None,
                "currency": "USD",
                "is_normalized": True,
                "is_complete": False,
            },
        },
        "timing": {
            "started_at": "2026-03-09T12:34:56.789Z",
            "completed_at": "2026-03-09T12:35:01.123Z",
            "duration_ms": 4334,
        },
    }
    result = RunResult.model_validate(data)
    assert result.status == "failed"
    assert result.final_answer is None
    assert result.error is not None
    assert result.error.code == "participant_quorum_lost"


def test_auth_set_result_validates() -> None:
    """Validate AuthSetResult shape from APPLICATION_PROTOCOL.md §5.6."""
    result = AuthSetResult.model_validate(
        {"saved": True, "storage_path": "~/.nelson/openrouter_api_key"}
    )
    dumped = json.loads(result.model_dump_json())
    assert dumped["saved"] is True
    assert dumped["storage_path"] == "~/.nelson/openrouter_api_key"


def test_auth_status_result_validates() -> None:
    """Validate AuthStatusResult shape."""
    result = AuthStatusResult.model_validate(
        {
            "saved_key_present": True,
            "env_key_present": False,
            "effective_source": "saved",
            "verification": "valid",
        }
    )
    dumped = json.loads(result.model_dump_json())
    assert dumped["saved_key_present"] is True
    assert dumped["effective_source"] == "saved"


def test_auth_clear_result_validates() -> None:
    """Validate AuthClearResult shape."""
    result = AuthClearResult.model_validate({"saved_key_removed": True})
    dumped = json.loads(result.model_dump_json())
    assert dumped["saved_key_removed"] is True
