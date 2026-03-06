from pydantic_ai import Agent

from app.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    DISAGREEMENT_SYSTEM_PROMPT,
    FINAL_SUMMARIZER_SYSTEM_PROMPT,
    RESPONDER_SYSTEM_PROMPT,
    SCORER_SYSTEM_PROMPT,
)
from app.agent.types import DisagreementCheck, InitialScore

# Streamed agents (output_type=str) — user-facing text
responder_agent = Agent(
    "openai:gpt-4o",
    output_type=str,
    system_prompt=RESPONDER_SYSTEM_PROMPT,
    defer_model_check=True,
)

critic_agent = Agent(
    "openai:gpt-4o",
    output_type=str,
    system_prompt=CRITIC_SYSTEM_PROMPT,
    defer_model_check=True,
)

final_summarizer_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=str,
    system_prompt=FINAL_SUMMARIZER_SYSTEM_PROMPT,
    defer_model_check=True,
)

# Non-streamed agents (structured output) — metadata extraction
scorer_agent = Agent(
    "openai:gpt-4o",
    output_type=InitialScore,
    system_prompt=SCORER_SYSTEM_PROMPT,
    defer_model_check=True,
)

disagreement_agent = Agent(
    "openai:gpt-4o",
    output_type=DisagreementCheck,
    system_prompt=DISAGREEMENT_SYSTEM_PROMPT,
    defer_model_check=True,
)
