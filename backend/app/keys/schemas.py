import uuid
from datetime import datetime

from pydantic import BaseModel


class StoreKeyRequest(BaseModel):
    provider_id: uuid.UUID
    api_key: str


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_slug: str
    provider_display_name: str
    masked_key: str
    is_valid: bool
    validated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidateKeyResponse(BaseModel):
    is_valid: bool
    error: str | None = None
