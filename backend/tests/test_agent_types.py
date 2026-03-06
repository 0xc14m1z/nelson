from app.agent.prompts import (
    build_critic_prompt,
    build_disagreement_prompt,
    build_final_summary_prompt,
    build_responder_prompt,
    build_scorer_prompt,
)
from app.agent.types import DisagreementCheck, InitialScore


def test_initial_score_schema():
    r = InitialScore(
        confidence=0.95,
        key_points=["point 1", "point 2"],
    )
    assert r.confidence == 0.95
    assert len(r.key_points) == 2


def test_disagreement_check_schema():
    r = DisagreementCheck(
        has_disagreements=True,
        disagreements=["disagree on X"],
    )
    assert r.has_disagreements is True
    assert len(r.disagreements) == 1


def test_build_responder_prompt():
    prompt = build_responder_prompt("What is 2+2?")
    assert "What is 2+2?" in prompt


def test_build_critic_prompt_with_disagreements():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        responses=[
            {"model_name": "GPT-4o", "response": "The answer is 4."},
            {"model_name": "Claude", "response": "It equals 4."},
        ],
        disagreements=["point A is wrong"],
    )
    assert "What is 2+2?" in prompt
    assert "GPT-4o" in prompt
    assert "Claude" in prompt
    assert "point A is wrong" in prompt


def test_build_critic_prompt_without_disagreements():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        responses=[{"model_name": "GPT-4o", "response": "4"}],
    )
    assert "Disagreements" not in prompt


def test_build_scorer_prompt():
    prompt = build_scorer_prompt("What is 2+2?", "The answer is 4.")
    assert "What is 2+2?" in prompt
    assert "The answer is 4." in prompt


def test_build_disagreement_prompt():
    prompt = build_disagreement_prompt(
        enquiry="What is 2+2?",
        responses=[
            {"model_name": "GPT-4o", "response": "Answer A"},
            {"model_name": "Claude", "response": "Answer B"},
        ],
    )
    assert "GPT-4o" in prompt
    assert "Answer B" in prompt


def test_build_final_summary_prompt():
    prompt = build_final_summary_prompt(
        enquiry="What is 2+2?",
        responses=[
            {"model_name": "GPT-4o", "response": "Answer A"},
            {"model_name": "Claude", "response": "Answer B"},
        ],
    )
    assert "GPT-4o" in prompt
    assert "Answer B" in prompt
    assert "synthesize" in prompt.lower() or "definitive" in prompt.lower()
