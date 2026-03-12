"""Domain model validation tests."""

import json

from nelson.protocols.domain import (
    ParticipantContribution,
    ReleaseGateResult,
    ReviewResult,
    TaskFramingResult,
    UsageSnapshot,
)


def test_task_framing_result_validates() -> None:
    """Validate shape from PROMPT_SPEC.md §4.3."""
    result = TaskFramingResult.model_validate(
        {
            "task_type": "analytical",
            "sensitivity": "low",
            "objective": "Provide a complete and accurate answer to the user's request",
            "quality_criteria": ["accuracy", "coverage", "clarity"],
            "aspects_to_cover": ["architecture", "testing", "packaging"],
            "ambiguities": [],
            "assumptions": [],
        }
    )
    dumped = json.loads(result.model_dump_json())
    assert dumped["task_type"] == "analytical"
    assert dumped["sensitivity"] == "low"
    assert len(dumped["quality_criteria"]) == 3


def test_participant_contribution_validates() -> None:
    """Validate shape from PROMPT_SPEC.md §5.3."""
    contribution = ParticipantContribution.model_validate(
        {
            "answer_markdown": "Main answer proposal in natural language",
            "assumptions": ["Python 3.14+ is required"],
            "limitations": ["Does not cover deployment"],
            "framing_feedback": {
                "status": "accept",
                "notes": [],
                "proposed_aspects": [],
            },
        }
    )
    dumped = json.loads(contribution.model_dump_json())
    assert dumped["answer_markdown"] == "Main answer proposal in natural language"
    assert dumped["framing_feedback"]["status"] == "accept"


def test_review_result_validates() -> None:
    """Validate shape from PROMPT_SPEC.md §7.3."""
    review = ReviewResult.model_validate(
        {
            "decision": "major_revise",
            "summary": "One core technical claim is unsupported",
            "required_changes": [
                "Remove or qualify the unsupported claim about deployment defaults"
            ],
            "optional_improvements": ["Clarify packaging recommendation"],
            "blocking_issues": ["The answer states a universal rule that depends on context"],
        }
    )
    dumped = json.loads(review.model_dump_json())
    assert dumped["decision"] == "major_revise"
    assert len(dumped["required_changes"]) == 1
    assert len(dumped["blocking_issues"]) == 1


def test_release_gate_result_validates() -> None:
    """Validate shape from PROMPT_SPEC.md §8.3."""
    gate = ReleaseGateResult.model_validate(
        {
            "decision": "pass_with_minor_fixes",
            "summary": "The answer is ready after a small caveat is added",
            "minor_fixes_applied": ["Added caveat about context dependence"],
            "blocking_issues": [],
            "final_answer_markdown": "Final deliverable answer",
        }
    )
    dumped = json.loads(gate.model_dump_json())
    assert dumped["decision"] == "pass_with_minor_fixes"
    assert dumped["final_answer_markdown"] == "Final deliverable answer"


def test_usage_snapshot_validates() -> None:
    """Validate shape from EVENT_SCHEMA.md §3.1."""
    usage = UsageSnapshot.model_validate(
        {
            "prompt_tokens": 1200,
            "completion_tokens": 450,
            "total_tokens": 1650,
            "cost_usd": None,
            "currency": "USD",
            "is_normalized": True,
            "is_complete": True,
        }
    )
    dumped = json.loads(usage.model_dump_json())
    assert dumped["prompt_tokens"] == 1200
    assert dumped["cost_usd"] is None
    assert dumped["is_complete"] is True
