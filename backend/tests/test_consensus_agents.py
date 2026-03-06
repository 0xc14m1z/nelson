import pytest
from pydantic_ai.models.test import TestModel

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary


async def test_responder_agent_returns_initial_response():
    with responder_agent.override(model=TestModel()):
        result = await responder_agent.run(build_responder_prompt("What is gravity?"))
        assert isinstance(result.output, InitialResponse)
        assert result.usage().requests >= 1


async def test_critic_agent_returns_critique_response():
    prompt = build_critic_prompt(
        enquiry="What is gravity?",
        prior_summary=None,
        responses=[{"model_name": "Model A", "response": "Gravity is a force."}],
    )
    with critic_agent.override(model=TestModel()):
        result = await critic_agent.run(prompt)
        assert isinstance(result.output, CritiqueResponse)
        assert isinstance(result.output.has_disagreements, bool)


async def test_summarizer_agent_returns_round_summary():
    prompt = build_summarizer_prompt(
        responses=[
            {"model_name": "Model A", "response": "Answer A"},
            {"model_name": "Model B", "response": "Answer B"},
        ]
    )
    with summarizer_agent.override(model=TestModel()):
        result = await summarizer_agent.run(prompt)
        assert isinstance(result.output, RoundSummary)
