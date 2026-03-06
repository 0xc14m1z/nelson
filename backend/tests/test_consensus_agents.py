import pytest
from pydantic_ai.models.test import TestModel

from app.agent.consensus_agent import (
    critic_agent,
    disagreement_agent,
    final_summarizer_agent,
    responder_agent,
    scorer_agent,
)
from app.agent.types import DisagreementCheck, InitialScore


@pytest.mark.asyncio
async def test_responder_agent_returns_str():
    with responder_agent.override(model=TestModel()):
        result = await responder_agent.run("What is 2+2?")
        assert isinstance(result.output, str)


@pytest.mark.asyncio
async def test_scorer_agent_returns_initial_score():
    with scorer_agent.override(model=TestModel()):
        result = await scorer_agent.run("Score this response")
        assert isinstance(result.output, InitialScore)


@pytest.mark.asyncio
async def test_critic_agent_returns_str():
    with critic_agent.override(model=TestModel()):
        result = await critic_agent.run("Critique these responses")
        assert isinstance(result.output, str)


@pytest.mark.asyncio
async def test_disagreement_agent_returns_check():
    with disagreement_agent.override(model=TestModel()):
        result = await disagreement_agent.run("Check disagreements")
        assert isinstance(result.output, DisagreementCheck)


@pytest.mark.asyncio
async def test_final_summarizer_returns_str():
    with final_summarizer_agent.override(model=TestModel()):
        result = await final_summarizer_agent.run("Summarize")
        assert isinstance(result.output, str)
