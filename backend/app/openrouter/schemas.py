import uuid
from decimal import Decimal

from pydantic import BaseModel


class AddCustomModelRequest(BaseModel):
    model_slug: str
    display_name: str
    model_type: str | None = None
    input_price_per_mtok: Decimal | None = None
    output_price_per_mtok: Decimal | None = None
    context_window: int | None = None
    tokens_per_second: float | None = None


class CustomModelResponse(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    model_type: str | None
    input_price_per_mtok: Decimal
    output_price_per_mtok: Decimal
    context_window: int
    tokens_per_second: float | None
    model_config = {"from_attributes": True}


class OpenRouterModelResponse(BaseModel):
    slug: str
    display_name: str
    model_type: str | None = None
    input_price_per_mtok: Decimal | None = None
    output_price_per_mtok: Decimal | None = None
    context_window: int | None = None
    tokens_per_second: float | None = None
