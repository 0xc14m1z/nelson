import uuid
from decimal import Decimal

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    base_url: str
    is_active: bool

    model_config = {"from_attributes": True}


class ModelResponse(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_slug: str
    slug: str
    display_name: str
    input_price_per_mtok: Decimal
    output_price_per_mtok: Decimal
    is_active: bool
    context_window: int

    model_config = {"from_attributes": True}
