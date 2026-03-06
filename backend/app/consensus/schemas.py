from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    enquiry: str = Field(min_length=1, max_length=10000)
    model_ids: list[UUID] = Field(min_length=2)
    max_rounds: int | None = Field(default=None, ge=2, le=20)


class SessionResponse(BaseModel):
    id: UUID
    enquiry: str
    status: str
    max_rounds: int | None
    current_round: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    total_duration_ms: int
    created_at: datetime
    completed_at: datetime | None
    model_ids: list[UUID]

    model_config = {"from_attributes": True}


class LLMCallResponse(BaseModel):
    id: UUID
    llm_model_id: UUID
    model_slug: str
    provider_slug: str
    round_number: int
    role: str
    prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    cost: float
    duration_ms: int
    error: str | None
    confidence: float | None
    key_points: list[str] | None
    has_disagreements: bool | None
    disagreements: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    llm_calls: list[LLMCallResponse]


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    page: int
    page_size: int
