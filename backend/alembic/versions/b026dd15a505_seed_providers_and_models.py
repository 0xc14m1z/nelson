"""seed providers and models

Revision ID: b026dd15a505
Revises: d7eb6b492f55
Create Date: 2026-03-04 23:10:34.967140

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b026dd15a505'
down_revision: Union[str, Sequence[str], None] = 'd7eb6b492f55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stable UUIDs for providers so we can reference them in model inserts
PROVIDER_IDS = {
    "openai": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "anthropic": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "google": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "mistral": uuid.UUID("10000000-0000-0000-0000-000000000004"),
    "openrouter": uuid.UUID("10000000-0000-0000-0000-000000000005"),
}

PROVIDERS = [
    {"id": PROVIDER_IDS["openai"], "slug": "openai", "display_name": "OpenAI", "base_url": "https://api.openai.com/v1"},
    {"id": PROVIDER_IDS["anthropic"], "slug": "anthropic", "display_name": "Anthropic", "base_url": "https://api.anthropic.com"},
    {"id": PROVIDER_IDS["google"], "slug": "google", "display_name": "Google", "base_url": "https://generativelanguage.googleapis.com/v1beta"},
    {"id": PROVIDER_IDS["mistral"], "slug": "mistral", "display_name": "Mistral", "base_url": "https://api.mistral.ai/v1"},
    {"id": PROVIDER_IDS["openrouter"], "slug": "openrouter", "display_name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
]

MODELS = [
    # OpenAI
    {"provider_id": PROVIDER_IDS["openai"], "slug": "gpt-4o", "display_name": "GPT-4o", "input_price_per_mtok": 2.50, "output_price_per_mtok": 10.00, "context_window": 128000},
    {"provider_id": PROVIDER_IDS["openai"], "slug": "gpt-4o-mini", "display_name": "GPT-4o Mini", "input_price_per_mtok": 0.15, "output_price_per_mtok": 0.60, "context_window": 128000},
    {"provider_id": PROVIDER_IDS["openai"], "slug": "o1", "display_name": "o1", "input_price_per_mtok": 15.00, "output_price_per_mtok": 60.00, "context_window": 200000},
    {"provider_id": PROVIDER_IDS["openai"], "slug": "o1-mini", "display_name": "o1 Mini", "input_price_per_mtok": 3.00, "output_price_per_mtok": 12.00, "context_window": 128000},
    # Anthropic
    {"provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4", "input_price_per_mtok": 3.00, "output_price_per_mtok": 15.00, "context_window": 200000},
    {"provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-haiku-3-5-20241022", "display_name": "Claude 3.5 Haiku", "input_price_per_mtok": 0.80, "output_price_per_mtok": 4.00, "context_window": 200000},
    {"provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-opus-4-20250514", "display_name": "Claude Opus 4", "input_price_per_mtok": 15.00, "output_price_per_mtok": 75.00, "context_window": 200000},
    # Google
    {"provider_id": PROVIDER_IDS["google"], "slug": "gemini-2.0-flash", "display_name": "Gemini 2.0 Flash", "input_price_per_mtok": 0.10, "output_price_per_mtok": 0.40, "context_window": 1000000},
    {"provider_id": PROVIDER_IDS["google"], "slug": "gemini-2.0-pro", "display_name": "Gemini 2.0 Pro", "input_price_per_mtok": 1.25, "output_price_per_mtok": 10.00, "context_window": 1000000},
    # Mistral
    {"provider_id": PROVIDER_IDS["mistral"], "slug": "mistral-large-latest", "display_name": "Mistral Large", "input_price_per_mtok": 2.00, "output_price_per_mtok": 6.00, "context_window": 128000},
    {"provider_id": PROVIDER_IDS["mistral"], "slug": "mistral-small-latest", "display_name": "Mistral Small", "input_price_per_mtok": 0.10, "output_price_per_mtok": 0.30, "context_window": 128000},
]


def upgrade() -> None:
    providers_table = sa.table(
        "providers",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("base_url", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(providers_table, [{**p, "is_active": True} for p in PROVIDERS])

    models_table = sa.table(
        "llm_models",
        sa.column("id", sa.Uuid),
        sa.column("provider_id", sa.Uuid),
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("input_price_per_mtok", sa.Numeric),
        sa.column("output_price_per_mtok", sa.Numeric),
        sa.column("is_active", sa.Boolean),
        sa.column("context_window", sa.Integer),
    )
    op.bulk_insert(
        models_table,
        [{**m, "id": uuid.uuid4(), "is_active": True} for m in MODELS],
    )


def downgrade() -> None:
    op.execute("DELETE FROM llm_models")
    op.execute("DELETE FROM providers")
