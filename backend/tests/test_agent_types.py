from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary


def test_initial_response_schema():
    r = InitialResponse(
        response="The answer is 42",
        confidence=0.95,
        key_points=["point 1", "point 2"],
    )
    assert r.confidence == 0.95
    assert len(r.key_points) == 2


def test_critique_response_schema():
    r = CritiqueResponse(
        has_disagreements=True,
        disagreements=["disagree on X"],
        revised_response="Updated answer",
    )
    assert r.has_disagreements is True


def test_round_summary_schema():
    r = RoundSummary(
        agreements=["agree on A"],
        disagreements=["disagree on B"],
        shifts=["shifted from C to D"],
        summary="Models mostly agree but differ on B.",
    )
    assert "agree on A" in r.agreements


def test_build_responder_prompt():
    prompt = build_responder_prompt("What is 2+2?")
    assert "What is 2+2?" in prompt


def test_build_critic_prompt_with_summary():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        prior_summary="Models agree it is 4.",
        responses=[
            {"model_name": "GPT-4o", "response": "The answer is 4."},
            {"model_name": "Claude", "response": "It equals 4."},
        ],
    )
    assert "What is 2+2?" in prompt
    assert "Models agree" in prompt
    assert "GPT-4o" in prompt
    assert "Claude" in prompt


def test_build_critic_prompt_without_summary():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        prior_summary=None,
        responses=[{"model_name": "GPT-4o", "response": "4"}],
    )
    assert "Summary of prior rounds" not in prompt


def test_build_summarizer_prompt():
    prompt = build_summarizer_prompt(
        responses=[
            {"model_name": "GPT-4o", "response": "Answer A"},
            {"model_name": "Claude", "response": "Answer B"},
        ]
    )
    assert "GPT-4o" in prompt
    assert "Answer B" in prompt
