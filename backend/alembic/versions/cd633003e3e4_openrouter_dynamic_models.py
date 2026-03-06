"""openrouter dynamic models

Revision ID: cd633003e3e4
Revises: 0ae6b35ef59c
Create Date: 2026-03-06 03:12:41.804731

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd633003e3e4"
down_revision: str | Sequence[str] | None = "0ae6b35ef59c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- Seed data constants ---

PROVIDER_IDS = {
    "openai": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "anthropic": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "google": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "mistral": uuid.UUID("10000000-0000-0000-0000-000000000004"),
    "openrouter": uuid.UUID("10000000-0000-0000-0000-000000000005"),
    "xai": uuid.UUID("10000000-0000-0000-0000-000000000006"),
}

MODEL_IDS = {
    "gpt-5": uuid.UUID("20000000-0000-0000-0000-000000000101"),
    "gpt-5-mini": uuid.UUID("20000000-0000-0000-0000-000000000102"),
    "o3": uuid.UUID("20000000-0000-0000-0000-000000000103"),
    "o4-mini": uuid.UUID("20000000-0000-0000-0000-000000000104"),
    "claude-opus-4-6": uuid.UUID("20000000-0000-0000-0000-000000000105"),
    "claude-sonnet-4-6": uuid.UUID("20000000-0000-0000-0000-000000000106"),
    "claude-haiku-4-5": uuid.UUID("20000000-0000-0000-0000-000000000107"),
    "gemini-3.1-pro": uuid.UUID("20000000-0000-0000-0000-000000000108"),
    "gemini-3.1-flash-lite": uuid.UUID("20000000-0000-0000-0000-000000000109"),
    "mistral-large-3": uuid.UUID("20000000-0000-0000-0000-000000000110"),
    "mistral-medium-3": uuid.UUID("20000000-0000-0000-0000-000000000111"),
    "deepseek/deepseek-v3.2": uuid.UUID("20000000-0000-0000-0000-000000000112"),
    "qwen/qwen3-coder": uuid.UUID("20000000-0000-0000-0000-000000000113"),
    "grok-3": uuid.UUID("20000000-0000-0000-0000-000000000114"),
}

MODELS = [
    # --- Anthropic ---
    {
        "id": MODEL_IDS["claude-opus-4-6"],
        "provider_id": PROVIDER_IDS["anthropic"],
        "slug": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6",
        "model_type": "hybrid",
        "input_price_per_mtok": 5.00,
        "output_price_per_mtok": 25.00,
        "context_window": 1000000,
    },
    {
        "id": MODEL_IDS["claude-sonnet-4-6"],
        "provider_id": PROVIDER_IDS["anthropic"],
        "slug": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "model_type": "hybrid",
        "input_price_per_mtok": 3.00,
        "output_price_per_mtok": 15.00,
        "context_window": 1000000,
    },
    {
        "id": MODEL_IDS["claude-haiku-4-5"],
        "provider_id": PROVIDER_IDS["anthropic"],
        "slug": "claude-haiku-4-5",
        "display_name": "Claude Haiku 4.5",
        "model_type": "chat",
        "input_price_per_mtok": 0.25,
        "output_price_per_mtok": 1.25,
        "context_window": 200000,
    },
    # --- OpenAI ---
    {
        "id": MODEL_IDS["gpt-5"],
        "provider_id": PROVIDER_IDS["openai"],
        "slug": "gpt-5",
        "display_name": "GPT-5",
        "model_type": "chat",
        "input_price_per_mtok": 1.25,
        "output_price_per_mtok": 10.00,
        "context_window": 400000,
    },
    {
        "id": MODEL_IDS["gpt-5-mini"],
        "provider_id": PROVIDER_IDS["openai"],
        "slug": "gpt-5-mini",
        "display_name": "GPT-5 Mini",
        "model_type": "chat",
        "input_price_per_mtok": 0.25,
        "output_price_per_mtok": 2.00,
        "context_window": 400000,
    },
    {
        "id": MODEL_IDS["o3"],
        "provider_id": PROVIDER_IDS["openai"],
        "slug": "o3",
        "display_name": "o3",
        "model_type": "reasoning",
        "input_price_per_mtok": 2.00,
        "output_price_per_mtok": 8.00,
        "context_window": 200000,
    },
    {
        "id": MODEL_IDS["o4-mini"],
        "provider_id": PROVIDER_IDS["openai"],
        "slug": "o4-mini",
        "display_name": "o4 Mini",
        "model_type": "reasoning",
        "input_price_per_mtok": 0,
        "output_price_per_mtok": 0,
        "context_window": 200000,
    },
    # --- Google ---
    {
        "id": MODEL_IDS["gemini-3.1-pro"],
        "provider_id": PROVIDER_IDS["google"],
        "slug": "gemini-3.1-pro",
        "display_name": "Gemini 3.1 Pro",
        "model_type": "hybrid",
        "input_price_per_mtok": 2.00,
        "output_price_per_mtok": 12.00,
        "context_window": 1000000,
    },
    {
        "id": MODEL_IDS["gemini-3.1-flash-lite"],
        "provider_id": PROVIDER_IDS["google"],
        "slug": "gemini-3.1-flash-lite",
        "display_name": "Gemini 3.1 Flash Lite",
        "model_type": "chat",
        "input_price_per_mtok": 0.25,
        "output_price_per_mtok": 1.50,
        "context_window": 1000000,
    },
    # --- Mistral ---
    {
        "id": MODEL_IDS["mistral-large-3"],
        "provider_id": PROVIDER_IDS["mistral"],
        "slug": "mistral-large-3",
        "display_name": "Mistral Large 3",
        "model_type": "chat",
        "input_price_per_mtok": 0.50,
        "output_price_per_mtok": 1.50,
        "context_window": 128000,
    },
    {
        "id": MODEL_IDS["mistral-medium-3"],
        "provider_id": PROVIDER_IDS["mistral"],
        "slug": "mistral-medium-3",
        "display_name": "Mistral Medium 3",
        "model_type": "chat",
        "input_price_per_mtok": 0.40,
        "output_price_per_mtok": 2.00,
        "context_window": 128000,
    },
    # --- xAI ---
    {
        "id": MODEL_IDS["grok-3"],
        "provider_id": PROVIDER_IDS["xai"],
        "slug": "grok-3",
        "display_name": "Grok 3",
        "model_type": "chat",
        "input_price_per_mtok": 3.00,
        "output_price_per_mtok": 15.00,
        "context_window": 131072,
    },
    # --- OpenRouter ---
    {
        "id": MODEL_IDS["deepseek/deepseek-v3.2"],
        "provider_id": PROVIDER_IDS["openrouter"],
        "slug": "deepseek/deepseek-v3.2",
        "display_name": "DeepSeek V3.2",
        "model_type": "hybrid",
        "input_price_per_mtok": 0.25,
        "output_price_per_mtok": 0.38,
        "context_window": 164000,
    },
    {
        "id": MODEL_IDS["qwen/qwen3-coder"],
        "provider_id": PROVIDER_IDS["openrouter"],
        "slug": "qwen/qwen3-coder",
        "display_name": "Qwen3 Coder",
        "model_type": "code",
        "input_price_per_mtok": 0.22,
        "output_price_per_mtok": 1.00,
        "context_window": 262000,
    },
]


def upgrade() -> None:
    """Upgrade schema."""
    # --- DDL: new tables ---
    op.create_table(
        "default_models",
        sa.Column("llm_model_id", sa.Uuid(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["llm_model_id"], ["llm_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("llm_model_id", name="uq_default_model"),
    )
    op.create_table(
        "user_custom_models",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("llm_model_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["llm_model_id"], ["llm_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "llm_model_id", name="uq_user_custom_model"),
    )
    op.create_index(
        op.f("ix_user_custom_models_user_id"),
        "user_custom_models",
        ["user_id"],
        unique=False,
    )

    # --- DDL: new columns on llm_models ---
    op.add_column("llm_models", sa.Column("model_type", sa.String(length=50), nullable=True))
    op.add_column("llm_models", sa.Column("tokens_per_second", sa.Float(), nullable=True))

    # --- Seed data: add xAI provider ---
    providers_table = sa.table(
        "providers",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("base_url", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        providers_table,
        [
            {
                "id": PROVIDER_IDS["xai"],
                "slug": "xai",
                "display_name": "xAI",
                "base_url": "https://api.x.ai/v1",
                "is_active": True,
            },
        ],
    )

    # --- Seed data: replace old models with 2026 frontier models ---
    # Clear tables that may reference llm_models (from consensus branch, if already applied)
    conn = op.get_bind()
    for table in ("llm_calls", "session_models"):
        result = conn.execute(sa.text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
        ), {"t": table})
        if result.scalar():
            conn.execute(sa.text(f"DELETE FROM {table}"))
    # Null out summarizer_model_id FK if user_settings has it
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'user_settings' AND column_name = 'summarizer_model_id'"
    ))
    if result.scalar():
        conn.execute(sa.text("UPDATE user_settings SET summarizer_model_id = NULL"))
    op.execute("DELETE FROM user_default_models")
    op.execute("DELETE FROM llm_models")

    models_table = sa.table(
        "llm_models",
        sa.column("id", sa.Uuid),
        sa.column("provider_id", sa.Uuid),
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("model_type", sa.String),
        sa.column("input_price_per_mtok", sa.Numeric),
        sa.column("output_price_per_mtok", sa.Numeric),
        sa.column("is_active", sa.Boolean),
        sa.column("context_window", sa.Integer),
    )
    op.bulk_insert(models_table, [{**m, "is_active": True} for m in MODELS])

    defaults_table = sa.table(
        "default_models",
        sa.column("id", sa.Uuid),
        sa.column("llm_model_id", sa.Uuid),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        defaults_table,
        [
            {"id": uuid.uuid4(), "llm_model_id": m["id"], "display_order": i}
            for i, m in enumerate(MODELS)
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- Remove seed data ---
    op.execute("DELETE FROM default_models")
    op.execute("DELETE FROM llm_models")

    # --- DDL: drop new columns ---
    op.drop_column("llm_models", "tokens_per_second")
    op.drop_column("llm_models", "model_type")

    # --- Remove xAI provider ---
    op.execute(f"DELETE FROM providers WHERE id = '{PROVIDER_IDS['xai']}'")

    # --- DDL: drop new tables ---
    op.drop_index(op.f("ix_user_custom_models_user_id"), table_name="user_custom_models")
    op.drop_table("user_custom_models")
    op.drop_table("default_models")
