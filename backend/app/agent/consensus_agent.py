from pydantic_ai import Agent

from app.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    RESPONDER_SYSTEM_PROMPT,
    SUMMARIZER_SYSTEM_PROMPT,
)
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary

responder_agent = Agent(
    "openai:gpt-4o",  # placeholder, overridden at runtime
    output_type=InitialResponse,
    system_prompt=RESPONDER_SYSTEM_PROMPT,
    defer_model_check=True,
)

critic_agent = Agent(
    "openai:gpt-4o",
    output_type=CritiqueResponse,
    system_prompt=CRITIC_SYSTEM_PROMPT,
    defer_model_check=True,
)

summarizer_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=RoundSummary,
    system_prompt=SUMMARIZER_SYSTEM_PROMPT,
    defer_model_check=True,
)
