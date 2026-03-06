from pydantic import BaseModel, Field


class InitialResponse(BaseModel):
    response: str = Field(description="Thorough answer to the enquiry")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level 0-1")
    key_points: list[str] = Field(description="Key points of the response")


class CritiqueResponse(BaseModel):
    has_disagreements: bool = Field(description="Whether disagreements remain with other models")
    disagreements: list[str] = Field(description="Specific points of disagreement")
    revised_response: str = Field(description="Updated answer incorporating valid points from others")


class RoundSummary(BaseModel):
    agreements: list[str] = Field(description="Points all models agree on")
    disagreements: list[str] = Field(description="Points where models still differ")
    shifts: list[str] = Field(description="What changed from the prior round")
    summary: str = Field(description="Concise prose summary of the round")
