from pydantic import BaseModel, Field


class InitialScore(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level 0-1")
    key_points: list[str] = Field(description="Key points of the response")


class DisagreementCheck(BaseModel):
    has_disagreements: bool = Field(description="Whether disagreements remain with other models")
    disagreements: list[str] = Field(description="Specific points of disagreement")
