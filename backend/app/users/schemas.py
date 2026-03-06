import uuid

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    billing_mode: str

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    billing_mode: str | None = None


class SettingsResponse(BaseModel):
    max_rounds: int | None = None
    default_model_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateSettingsRequest(BaseModel):
    max_rounds: int | None = None
    default_model_ids: list[uuid.UUID] = Field(default_factory=list)
