# OpenRouter Dynamic Models — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Normalize the DB schema (llm_models + default_models + user_custom_models), update seed data to current 2026 frontier models, add OpenRouter model search/browse proxy, custom model CRUD, and restructure the frontend settings page.

**Architecture:** Three-table normalized design. `llm_models` is the single source of truth for all model metadata. `default_models` is a thin join table for the curated catalog. `user_custom_models` links users to models they added from OpenRouter. New `/api/openrouter/models` endpoint proxies to OpenRouter's API for search/browse. Frontend adds an "Add from OpenRouter" modal to the Default Models tab.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy (async), Alembic, httpx, pytest-asyncio, Next.js, React, Mantine UI, React Query, Vitest

---

### Task 1: Alembic Migration — Schema Changes + Seed Data Update

**Files:**
- Create: `backend/alembic/versions/<auto>_openrouter_dynamic_models.py`
- Modify: `backend/app/models/llm_model.py`
- Modify: `backend/app/models/__init__.py`

This migration does four things:
1. Add `model_type` (VARCHAR 50, nullable) and `tokens_per_second` (FLOAT, nullable) columns to `llm_models`
2. Create `default_models` table (id UUID PK, llm_model_id UUID FK unique, display_order INTEGER)
3. Create `user_custom_models` table (id UUID PK, user_id UUID FK, llm_model_id UUID FK, created_at TIMESTAMP; unique on user_id+llm_model_id)
4. Delete old seed data, insert updated models, populate `default_models` with all seeded model IDs

**Step 1: Update the LLMModel ORM class**

Add `model_type` and `tokens_per_second` columns to `backend/app/models/llm_model.py`:

```python
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class LLMModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "llm_models"
    __table_args__ = (UniqueConstraint("provider_id", "slug", name="uq_provider_slug"),)

    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_price_per_mtok: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    output_price_per_mtok: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False, default=128000)
    tokens_per_second: Mapped[float | None] = mapped_column(Float, nullable=True)

    provider: Mapped["Provider"] = relationship(back_populates="models")  # noqa: F821, UP037
```

**Step 2: Create DefaultModel and UserCustomModel ORM classes**

Create `backend/app/models/default_model.py`:

```python
import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKey


class DefaultModel(UUIDPrimaryKey, Base):
    __tablename__ = "default_models"
    __table_args__ = (UniqueConstraint("llm_model_id", name="uq_default_model"),)

    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    llm_model: Mapped["LLMModel"] = relationship()  # noqa: F821, UP037
```

Create `backend/app/models/user_custom_model.py`:

```python
import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class UserCustomModel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "user_custom_models"
    __table_args__ = (
        UniqueConstraint("user_id", "llm_model_id", name="uq_user_custom_model"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )

    llm_model: Mapped["LLMModel"] = relationship()  # noqa: F821, UP037
```

**Step 3: Update `backend/app/models/__init__.py`**

Add exports for `DefaultModel` and `UserCustomModel`:

```python
from app.models.api_key import ApiKey
from app.models.base import Base
from app.models.default_model import DefaultModel
from app.models.llm_model import LLMModel
from app.models.magic_link import MagicLink
from app.models.provider import Provider
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserSettings, user_default_models
from app.models.user_custom_model import UserCustomModel

__all__ = [
    "ApiKey",
    "Base",
    "DefaultModel",
    "LLMModel",
    "MagicLink",
    "Provider",
    "RefreshToken",
    "User",
    "UserCustomModel",
    "UserSettings",
    "user_default_models",
]
```

**Step 4: Generate and edit the Alembic migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "openrouter dynamic models"`

Then edit the generated migration to also handle seed data. The migration should:

1. Auto-generated: add `model_type` and `tokens_per_second` columns to `llm_models`, create `default_models` and `user_custom_models` tables
2. Manually add: delete old seed data from `llm_models`, insert updated models, populate `default_models`

Add this seed data logic to the `upgrade()` function after the auto-generated DDL:

```python
# --- Seed data update ---
# Delete old model seed data (cascade will handle user_default_models refs)
op.execute("DELETE FROM user_default_models")
op.execute("DELETE FROM llm_models")

PROVIDER_IDS = {
    "openai": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "anthropic": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "google": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "mistral": uuid.UUID("10000000-0000-0000-0000-000000000004"),
    "openrouter": uuid.UUID("10000000-0000-0000-0000-000000000005"),
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
}

MODELS = [
    # OpenAI
    {"id": MODEL_IDS["gpt-5"], "provider_id": PROVIDER_IDS["openai"], "slug": "gpt-5", "display_name": "GPT-5", "model_type": "chat", "input_price_per_mtok": 1.25, "output_price_per_mtok": 10.00, "context_window": 400000},
    {"id": MODEL_IDS["gpt-5-mini"], "provider_id": PROVIDER_IDS["openai"], "slug": "gpt-5-mini", "display_name": "GPT-5 Mini", "model_type": "chat", "input_price_per_mtok": 0.25, "output_price_per_mtok": 2.00, "context_window": 400000},
    {"id": MODEL_IDS["o3"], "provider_id": PROVIDER_IDS["openai"], "slug": "o3", "display_name": "o3", "model_type": "reasoning", "input_price_per_mtok": 2.00, "output_price_per_mtok": 8.00, "context_window": 200000},
    {"id": MODEL_IDS["o4-mini"], "provider_id": PROVIDER_IDS["openai"], "slug": "o4-mini", "display_name": "o4 Mini", "model_type": "reasoning", "input_price_per_mtok": 0, "output_price_per_mtok": 0, "context_window": 200000},
    # Anthropic
    {"id": MODEL_IDS["claude-opus-4-6"], "provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "model_type": "hybrid", "input_price_per_mtok": 5.00, "output_price_per_mtok": 25.00, "context_window": 1000000},
    {"id": MODEL_IDS["claude-sonnet-4-6"], "provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "model_type": "hybrid", "input_price_per_mtok": 3.00, "output_price_per_mtok": 15.00, "context_window": 1000000},
    {"id": MODEL_IDS["claude-haiku-4-5"], "provider_id": PROVIDER_IDS["anthropic"], "slug": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "model_type": "chat", "input_price_per_mtok": 0.25, "output_price_per_mtok": 1.25, "context_window": 200000},
    # Google
    {"id": MODEL_IDS["gemini-3.1-pro"], "provider_id": PROVIDER_IDS["google"], "slug": "gemini-3.1-pro", "display_name": "Gemini 3.1 Pro", "model_type": "hybrid", "input_price_per_mtok": 2.00, "output_price_per_mtok": 12.00, "context_window": 1000000},
    {"id": MODEL_IDS["gemini-3.1-flash-lite"], "provider_id": PROVIDER_IDS["google"], "slug": "gemini-3.1-flash-lite", "display_name": "Gemini 3.1 Flash Lite", "model_type": "chat", "input_price_per_mtok": 0.25, "output_price_per_mtok": 1.50, "context_window": 1000000},
    # Mistral
    {"id": MODEL_IDS["mistral-large-3"], "provider_id": PROVIDER_IDS["mistral"], "slug": "mistral-large-3", "display_name": "Mistral Large 3", "model_type": "chat", "input_price_per_mtok": 0.50, "output_price_per_mtok": 1.50, "context_window": 128000},
    {"id": MODEL_IDS["mistral-medium-3"], "provider_id": PROVIDER_IDS["mistral"], "slug": "mistral-medium-3", "display_name": "Mistral Medium 3", "model_type": "chat", "input_price_per_mtok": 0.40, "output_price_per_mtok": 2.00, "context_window": 128000},
    # OpenRouter
    {"id": MODEL_IDS["deepseek/deepseek-v3.2"], "provider_id": PROVIDER_IDS["openrouter"], "slug": "deepseek/deepseek-v3.2", "display_name": "DeepSeek V3.2", "model_type": "hybrid", "input_price_per_mtok": 0.25, "output_price_per_mtok": 0.38, "context_window": 164000},
    {"id": MODEL_IDS["qwen/qwen3-coder"], "provider_id": PROVIDER_IDS["openrouter"], "slug": "qwen/qwen3-coder", "display_name": "Qwen3 Coder", "model_type": "code", "input_price_per_mtok": 0.22, "output_price_per_mtok": 1.00, "context_window": 262000},
]

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

# Populate default_models with all seeded models
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
```

The `downgrade()` should reverse: drop tables, remove columns, re-insert old seed data (or just reference the old seed migration).

**Step 5: Run the migration**

Run: `cd backend && uv run alembic upgrade head`

**Step 6: Verify migration applied**

Run: `cd backend && uv run python -c "from app.database import engine; import asyncio; asyncio.run(engine.dispose())"`

**Step 7: Commit**

```bash
git add backend/app/models/llm_model.py backend/app/models/default_model.py backend/app/models/user_custom_model.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add default_models + user_custom_models tables, update seed data to 2026 frontier models"
```

---

### Task 2: Update Catalog Schemas + Router for New Fields

**Files:**
- Modify: `backend/app/catalog/schemas.py`
- Modify: `backend/app/catalog/router.py`
- Modify: `backend/tests/test_catalog_router.py`

**Step 1: Write failing tests**

Update `backend/tests/test_catalog_router.py` to check for new fields and updated model count:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_providers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/providers")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) == 5
        slugs = {p["slug"] for p in providers}
        assert slugs == {"openai", "anthropic", "google", "mistral", "openrouter"}


@pytest.mark.asyncio
async def test_list_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/models")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) == 13  # updated from 11


@pytest.mark.asyncio
async def test_list_models_filtered_by_provider():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        providers_resp = await client.get("/api/providers")
        openai = next(p for p in providers_resp.json() if p["slug"] == "openai")

        resp = await client.get(f"/api/models?provider_id={openai['id']}")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) == 4
        assert all(m["provider_slug"] == "openai" for m in models)


@pytest.mark.asyncio
async def test_model_response_includes_new_fields():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/models")
        models = resp.json()
        # Find a model with known type
        opus = next(m for m in models if m["slug"] == "claude-opus-4-6")
        assert opus["model_type"] == "hybrid"
        assert "tokens_per_second" in opus
        assert opus["context_window"] == 1000000
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_catalog_router.py -v`
Expected: FAIL — `model_type` and `tokens_per_second` not in ModelResponse, model count is wrong

**Step 3: Update schemas**

Update `backend/app/catalog/schemas.py`:

```python
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
    model_type: str | None
    input_price_per_mtok: Decimal
    output_price_per_mtok: Decimal
    is_active: bool
    context_window: int
    tokens_per_second: float | None

    model_config = {"from_attributes": True}
```

**Step 4: Update catalog router**

Update `backend/app/catalog/router.py` — add `model_type` and `tokens_per_second` to the ModelResponse construction:

```python
return [
    ModelResponse(
        id=m.id,
        provider_id=m.provider_id,
        provider_slug=m.provider.slug,
        slug=m.slug,
        display_name=m.display_name,
        model_type=m.model_type,
        input_price_per_mtok=m.input_price_per_mtok,
        output_price_per_mtok=m.output_price_per_mtok,
        is_active=m.is_active,
        context_window=m.context_window,
        tokens_per_second=m.tokens_per_second,
    )
    for m in models
]
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_router.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/catalog/schemas.py backend/app/catalog/router.py backend/tests/test_catalog_router.py
git commit -m "feat: add model_type and tokens_per_second to catalog API"
```

---

### Task 3: Update Model Registry Tests for New Slugs

**Files:**
- Modify: `backend/tests/test_model_registry.py`

The model registry tests reference old slugs (`gpt-4o`). Update them to use new slugs (`gpt-5`).

**Step 1: Update test_model_registry.py**

Replace all references to `gpt-4o` with `gpt-5` in `backend/tests/test_model_registry.py`:

- `_get_model(session, "gpt-4o")` → `_get_model(session, "gpt-5")`
- `assert resolved.model_slug == "gpt-4o"` → `assert resolved.model_slug == "gpt-5"`
- `assert resolved.model_slug == "openai/gpt-4o"` → `assert resolved.model_slug == "openai/gpt-5"`

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_model_registry.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_model_registry.py
git commit -m "test: update model registry tests for new model slugs"
```

---

### Task 4: Custom Models Backend — Service + Router

**Files:**
- Create: `backend/app/openrouter/__init__.py`
- Create: `backend/app/openrouter/router.py`
- Create: `backend/app/openrouter/service.py`
- Create: `backend/app/openrouter/schemas.py`
- Modify: `backend/app/main.py`

**Step 1: Write failing tests**

Create `backend/tests/test_custom_models.py`:

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.keys.service import store_key
from app.models import LLMModel, Provider, User, UserSettings, UserCustomModel


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"custom-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


async def _get_provider(session: AsyncSession, slug: str) -> Provider:
    result = await session.execute(select(Provider).where(Provider.slug == slug))
    return result.scalar_one()


async def _auth_headers(session: AsyncSession, user: User) -> dict:
    """Get JWT auth headers for a user. Uses the auth flow."""
    from app.auth.service import create_access_token
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_add_custom_model(client):
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(user.id, openrouter.id, "sk-or-test", session, skip_validation=True)
        await session.commit()

        from app.auth.service import create_access_token
        token = create_access_token(user.id)

        resp = await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "meta-llama/llama-3.1-405b",
                "display_name": "Llama 3.1 405B",
                "model_type": "chat",
                "input_price_per_mtok": 0.50,
                "output_price_per_mtok": 1.00,
                "context_window": 131072,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "meta-llama/llama-3.1-405b"
        assert data["display_name"] == "Llama 3.1 405B"
        assert data["model_type"] == "chat"


@pytest.mark.asyncio
async def test_add_duplicate_custom_model_returns_409(client):
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(user.id, openrouter.id, "sk-or-test", session, skip_validation=True)
        await session.commit()

        from app.auth.service import create_access_token
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        body = {
            "model_slug": "meta-llama/llama-3.1-405b-dup",
            "display_name": "Llama 3.1 405B",
        }

        resp1 = await client.post("/api/users/me/custom-models", json=body, headers=headers)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/users/me/custom-models", json=body, headers=headers)
        assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_delete_custom_model(client):
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(user.id, openrouter.id, "sk-or-test", session, skip_validation=True)
        await session.commit()

        from app.auth.service import create_access_token
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # Add a model first
        resp = await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "meta-llama/llama-del-test",
                "display_name": "Llama Delete Test",
            },
            headers=headers,
        )
        model_id = resp.json()["id"]

        # Delete it
        del_resp = await client.delete(
            f"/api/users/me/custom-models/{model_id}",
            headers=headers,
        )
        assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_list_custom_models(client):
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(user.id, openrouter.id, "sk-or-test", session, skip_validation=True)
        await session.commit()

        from app.auth.service import create_access_token
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # Add a model
        await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "meta-llama/llama-list-test",
                "display_name": "Llama List Test",
            },
            headers=headers,
        )

        # List custom models
        resp = await client.get("/api/users/me/custom-models", headers=headers)
        assert resp.status_code == 200
        models = resp.json()
        assert any(m["slug"] == "meta-llama/llama-list-test" for m in models)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_custom_models.py -v`
Expected: FAIL — module/endpoint not found

**Step 3: Create schemas**

Create `backend/app/openrouter/__init__.py` (empty file).

Create `backend/app/openrouter/schemas.py`:

```python
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
    """Model from OpenRouter's /api/v1/models endpoint, mapped to our schema."""
    slug: str
    display_name: str
    model_type: str | None = None
    input_price_per_mtok: Decimal | None = None
    output_price_per_mtok: Decimal | None = None
    context_window: int | None = None
    tokens_per_second: float | None = None
```

**Step 4: Create service**

Create `backend/app/openrouter/service.py`:

```python
import uuid
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keys.service import get_decrypted_key
from app.models import LLMModel, Provider, UserCustomModel


async def get_openrouter_key(user_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Get the user's decrypted OpenRouter API key."""
    result = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
    provider = result.scalar_one_or_none()
    if not provider:
        return None
    return await get_decrypted_key(user_id, provider.id, db)


async def search_openrouter_models(api_key: str, search: str | None = None) -> list[dict]:
    """Fetch models from OpenRouter API and map to our schema."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()

    data = resp.json().get("data", [])

    models = []
    for m in data:
        model_id = m.get("id", "")
        name = m.get("name", model_id)
        pricing = m.get("pricing", {})

        # OpenRouter prices are per-token; convert to per-million-token
        input_price = Decimal(str(pricing.get("prompt", "0"))) * 1_000_000
        output_price = Decimal(str(pricing.get("completion", "0"))) * 1_000_000

        context_length = m.get("context_length")

        # Infer model_type from architecture or description
        arch = m.get("architecture", {})
        instruct_type = arch.get("instruct_type", "")
        model_type = "chat"
        if "reasoning" in name.lower() or "r1" in model_id.lower() or "o3" in model_id.lower():
            model_type = "reasoning"
        elif "code" in model_id.lower() or "coder" in model_id.lower():
            model_type = "code"

        entry = {
            "slug": model_id,
            "display_name": name,
            "model_type": model_type,
            "input_price_per_mtok": input_price,
            "output_price_per_mtok": output_price,
            "context_window": context_length,
            "tokens_per_second": None,  # OpenRouter doesn't provide this in /models
        }
        models.append(entry)

    if search:
        search_lower = search.lower()
        models = [m for m in models if search_lower in m["slug"].lower() or search_lower in m["display_name"].lower()]

    return models


async def add_custom_model(
    user_id: uuid.UUID,
    model_slug: str,
    display_name: str,
    db: AsyncSession,
    model_type: str | None = None,
    input_price_per_mtok: Decimal | None = None,
    output_price_per_mtok: Decimal | None = None,
    context_window: int | None = None,
    tokens_per_second: float | None = None,
) -> LLMModel:
    """Add a custom model: upsert into llm_models, create user_custom_models link."""
    # Get OpenRouter provider
    result = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
    openrouter = result.scalar_one()

    # Upsert into llm_models (check by provider_id + slug)
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.provider_id == openrouter.id,
            LLMModel.slug == model_slug,
        )
    )
    llm_model = result.scalar_one_or_none()

    if not llm_model:
        llm_model = LLMModel(
            provider_id=openrouter.id,
            slug=model_slug,
            display_name=display_name,
            model_type=model_type,
            input_price_per_mtok=input_price_per_mtok or Decimal("0"),
            output_price_per_mtok=output_price_per_mtok or Decimal("0"),
            context_window=context_window or 128000,
            tokens_per_second=tokens_per_second,
        )
        db.add(llm_model)
        await db.flush()

    # Check if user already has this custom model
    result = await db.execute(
        select(UserCustomModel).where(
            UserCustomModel.user_id == user_id,
            UserCustomModel.llm_model_id == llm_model.id,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Model already added")

    # Create user_custom_models link
    link = UserCustomModel(user_id=user_id, llm_model_id=llm_model.id)
    db.add(link)
    await db.flush()

    return llm_model


async def list_custom_models(user_id: uuid.UUID, db: AsyncSession) -> list[LLMModel]:
    """List all custom models for a user."""
    result = await db.execute(
        select(LLMModel)
        .join(UserCustomModel, UserCustomModel.llm_model_id == LLMModel.id)
        .where(UserCustomModel.user_id == user_id)
        .order_by(LLMModel.display_name)
    )
    return list(result.scalars().all())


async def delete_custom_model(
    user_id: uuid.UUID, model_id: uuid.UUID, db: AsyncSession
) -> bool:
    """Remove a custom model link. Also removes from user_default_models."""
    from app.models.user import user_default_models

    # Delete user_default_models reference
    await db.execute(
        user_default_models.delete().where(
            user_default_models.c.user_id == user_id,
            user_default_models.c.llm_model_id == model_id,
        )
    )

    # Delete user_custom_models link
    result = await db.execute(
        select(UserCustomModel).where(
            UserCustomModel.user_id == user_id,
            UserCustomModel.llm_model_id == model_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return False

    await db.delete(link)
    await db.flush()
    return True
```

**Step 5: Create router**

Create `backend/app/openrouter/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_id
from app.database import get_db
from app.openrouter.schemas import (
    AddCustomModelRequest,
    CustomModelResponse,
    OpenRouterModelResponse,
)
from app.openrouter.service import (
    add_custom_model,
    delete_custom_model,
    get_openrouter_key,
    list_custom_models,
    search_openrouter_models,
)

router = APIRouter(tags=["openrouter"])


@router.get("/api/openrouter/models", response_model=list[OpenRouterModelResponse])
async def browse_openrouter_models(
    search: str | None = Query(None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    api_key = await get_openrouter_key(user_id, db)
    if not api_key:
        raise HTTPException(status_code=401, detail="No OpenRouter API key configured")

    return await search_openrouter_models(api_key, search)


@router.get("/api/users/me/custom-models", response_model=list[CustomModelResponse])
async def list_user_custom_models(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    models = await list_custom_models(user_id, db)
    return [
        CustomModelResponse(
            id=m.id,
            slug=m.slug,
            display_name=m.display_name,
            model_type=m.model_type,
            input_price_per_mtok=m.input_price_per_mtok,
            output_price_per_mtok=m.output_price_per_mtok,
            context_window=m.context_window,
            tokens_per_second=m.tokens_per_second,
        )
        for m in models
    ]


@router.post(
    "/api/users/me/custom-models",
    response_model=CustomModelResponse,
    status_code=201,
)
async def add_user_custom_model(
    body: AddCustomModelRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        model = await add_custom_model(
            user_id=user_id,
            model_slug=body.model_slug,
            display_name=body.display_name,
            db=db,
            model_type=body.model_type,
            input_price_per_mtok=body.input_price_per_mtok,
            output_price_per_mtok=body.output_price_per_mtok,
            context_window=body.context_window,
            tokens_per_second=body.tokens_per_second,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Model already added")

    return CustomModelResponse(
        id=model.id,
        slug=model.slug,
        display_name=model.display_name,
        model_type=model.model_type,
        input_price_per_mtok=model.input_price_per_mtok,
        output_price_per_mtok=model.output_price_per_mtok,
        context_window=model.context_window,
        tokens_per_second=model.tokens_per_second,
    )


@router.delete("/api/users/me/custom-models/{model_id}", status_code=204)
async def remove_user_custom_model(
    model_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_custom_model(user_id, model_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Custom model not found")
```

**Step 6: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.openrouter.router import router as openrouter_router
# ...
app.include_router(openrouter_router)
```

**Step 7: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_custom_models.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/openrouter/ backend/app/main.py backend/tests/test_custom_models.py
git commit -m "feat: add custom model CRUD and OpenRouter search endpoint"
```

---

### Task 5: Update User Settings to Support Custom Models

**Files:**
- Modify: `backend/app/users/service.py`
- Create: `backend/tests/test_custom_models_settings.py`

The `update_settings` function currently validates model IDs against `llm_models` where `is_active=True`. This already works for custom models since they're stored in `llm_models`. No code change needed for validation — just add a test to confirm.

**Step 1: Write a test that selects a custom model as a default**

Create `backend/tests/test_custom_models_settings.py`:

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.keys.service import store_key
from app.models import Provider, User, UserSettings
from app.openrouter.service import add_custom_model
from app.users.service import get_settings, update_settings


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"settings-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


async def _get_provider(session: AsyncSession, slug: str) -> Provider:
    result = await session.execute(select(Provider).where(Provider.slug == slug))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_custom_model_can_be_selected_as_default():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(user.id, openrouter.id, "sk-or-test", session, skip_validation=True)

        model = await add_custom_model(
            user_id=user.id,
            model_slug="test/custom-model",
            display_name="Custom Test Model",
            db=session,
        )

        result = await update_settings(
            user_id=user.id,
            max_rounds=None,
            default_model_ids=[model.id],
            db=session,
        )
        assert model.id in result["default_model_ids"]

        settings = await get_settings(user.id, session)
        assert model.id in settings["default_model_ids"]

        await session.rollback()
```

**Step 2: Run test**

Run: `cd backend && uv run pytest tests/test_custom_models_settings.py -v`
Expected: PASS (no code changes needed — validates existing behavior)

**Step 3: Commit**

```bash
git add backend/tests/test_custom_models_settings.py
git commit -m "test: verify custom models work as user defaults"
```

---

### Task 6: Update Model Registry for OpenRouter-Native Models

**Files:**
- Modify: `backend/app/agent/model_registry.py`
- Modify: `backend/tests/test_model_registry.py`

OpenRouter-native models (provider_slug="openrouter") should route directly through OpenRouter using their slug as-is (e.g. `deepseek/deepseek-v3.2`), not get prefixed with `openrouter/`.

The current code already handles this correctly — line 59 of `model_registry.py` skips the OpenRouter fallback when `provider.slug == "openrouter"`, and step 1 (direct key) handles it. But we should add a test to confirm this works for curated OpenRouter models.

**Step 1: Write failing test**

Add to `backend/tests/test_model_registry.py`:

```python
@pytest.mark.asyncio
async def test_resolve_openrouter_native_model():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        model = await _get_model(session, "deepseek/deepseek-v3.2")

        await store_key(user.id, openrouter.id, "sk-or-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.api_key == "sk-or-key"
        assert resolved.base_url == "https://openrouter.ai/api/v1"
        assert resolved.model_slug == "deepseek/deepseek-v3.2"  # NOT prefixed
        assert resolved.provider_slug == "openrouter"
        assert resolved.via_openrouter is False  # direct key, not fallback
        await session.rollback()
```

**Step 2: Run tests**

Run: `cd backend && uv run pytest tests/test_model_registry.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_model_registry.py
git commit -m "test: verify OpenRouter-native model resolution"
```

---

### Task 7: Frontend — Update Types and Hooks

**Files:**
- Modify: `frontend/src/lib/hooks.ts`

**Step 1: Update the Model interface and add custom model hooks**

Update `frontend/src/lib/hooks.ts`:

Add `model_type` and `tokens_per_second` to the `Model` interface:

```typescript
export interface Model {
  id: string;
  provider_id: string;
  provider_slug: string;
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string;
  output_price_per_mtok: string;
  is_active: boolean;
  context_window: number;
  tokens_per_second: number | null;
}
```

Add a `CustomModel` interface (same fields minus provider_id/provider_slug/is_active):

```typescript
export interface CustomModel {
  id: string;
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string;
  output_price_per_mtok: string;
  context_window: number;
  tokens_per_second: number | null;
}
```

Add an `OpenRouterModel` interface:

```typescript
export interface OpenRouterModel {
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string | null;
  output_price_per_mtok: string | null;
  context_window: number | null;
  tokens_per_second: number | null;
}
```

Add hooks:

```typescript
export function useCustomModels() {
  return useQuery<CustomModel[]>({
    queryKey: ["customModels"],
    queryFn: async () => {
      const resp = await apiFetch("/api/users/me/custom-models");
      if (!resp.ok) throw new Error("Failed to fetch custom models");
      return resp.json();
    },
  });
}

export function useOpenRouterModels(search: string) {
  return useQuery<OpenRouterModel[]>({
    queryKey: ["openrouterModels", search],
    queryFn: async () => {
      const url = search
        ? `/api/openrouter/models?search=${encodeURIComponent(search)}`
        : "/api/openrouter/models";
      const resp = await apiFetch(url);
      if (!resp.ok) throw new Error("Failed to fetch OpenRouter models");
      return resp.json();
    },
    enabled: search.length >= 2,
  });
}

export function useAddCustomModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (model: {
      model_slug: string;
      display_name: string;
      model_type?: string | null;
      input_price_per_mtok?: number | null;
      output_price_per_mtok?: number | null;
      context_window?: number | null;
      tokens_per_second?: number | null;
    }) => {
      const resp = await apiFetch("/api/users/me/custom-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(model),
      });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "Failed to add model");
      }
      return resp.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customModels"] }),
  });
}

export function useDeleteCustomModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (modelId: string) => {
      const resp = await apiFetch(`/api/users/me/custom-models/${modelId}`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error("Failed to delete custom model");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customModels"] }),
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/hooks.ts
git commit -m "feat: add custom model hooks and update Model interface"
```

---

### Task 8: Frontend — Restructure Default Models Tab + Add OpenRouter Modal

**Files:**
- Modify: `frontend/src/app/(protected)/settings/page.tsx`

This is the largest frontend change. The DefaultModelsTab needs:
1. Curated models section with metadata (model_type badge, pricing, context window)
2. Divider + "Your custom models" section
3. "Add from OpenRouter" button → modal with search + browse tabs

**Step 1: Implement the restructured DefaultModelsTab**

Update `frontend/src/app/(protected)/settings/page.tsx`. Key changes:

- Import new hooks: `useCustomModels`, `useAddCustomModel`, `useDeleteCustomModel`, `useOpenRouterModels`
- Import additional Mantine components: `Divider`, `ActionIcon`, `Loader`, `ScrollArea`
- Add `ModelCard` helper component that shows: display_name, model_type badge, pricing, context window, tokens/sec
- Split the tab into curated models (from `useModels`) and custom models (from `useCustomModels`)
- Add "Add from OpenRouter" button and modal with search input and results list
- Each search result has an "Add" button that calls `useAddCustomModel`
- Each custom model has a "Remove" button that calls `useDeleteCustomModel`

The implementation should:

a) **ModelMetadata** — inline component showing badges for model_type, price, context:
```tsx
function ModelMetadata({ model }: { model: Model | CustomModel }) {
  return (
    <Group gap="xs">
      {model.model_type && (
        <Badge size="xs" variant="light" color={
          model.model_type === "reasoning" ? "violet" :
          model.model_type === "hybrid" ? "blue" :
          model.model_type === "code" ? "green" :
          "gray"
        }>
          {model.model_type}
        </Badge>
      )}
      <Text size="xs" c="dimmed">
        ${model.input_price_per_mtok}/${model.output_price_per_mtok} per M tokens
      </Text>
      <Text size="xs" c="dimmed">
        {(model.context_window / 1000).toFixed(0)}K context
      </Text>
    </Group>
  );
}
```

b) **DefaultModelsTab** — updated with custom models section:
- Top: curated models grouped by provider (unchanged structure, but now with ModelMetadata)
- Divider: "Your custom models"
- Custom models with checkboxes + remove button
- "Add from OpenRouter" button (disabled if no OpenRouter key)
- Save button covers both curated and custom model selections

c) **AddFromOpenRouterModal** — new component:
- Search input (debounced 300ms)
- Results list showing matching OpenRouter models with metadata
- "Add" button per result, disabled if already added
- Loading state while searching

**Step 2: Run frontend tests**

Run: `cd frontend && bun test`
Expected: Existing tests may need updates for new model count/fields. Update mocks accordingly.

**Step 3: Run dev server and manually verify**

Run: `docker compose up` and check the settings page at `http://localhost:3000/settings`

**Step 4: Commit**

```bash
git add frontend/src/app/\(protected\)/settings/page.tsx
git commit -m "feat: restructure Default Models tab with custom models + OpenRouter modal"
```

---

### Task 9: Update Frontend Tests

**Files:**
- Modify: `frontend/src/app/(protected)/settings/__tests__/page.test.tsx`

Update the existing settings page tests to account for:
- New model fields (`model_type`, `tokens_per_second`)
- New model count (13 instead of 11)
- New hooks being called (`useCustomModels`)
- Custom models section rendering

Update mock data in the test file to include the new fields. Add a test that verifies the "Add from OpenRouter" button appears when the user has an OpenRouter key.

**Step 1: Update test mocks and assertions**

Update model mock data to include `model_type` and `tokens_per_second`. Update any model count assertions.

**Step 2: Run tests**

Run: `cd frontend && bun test`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/app/\(protected\)/settings/__tests__/page.test.tsx
git commit -m "test: update settings page tests for custom models"
```

---

### Task 10: Run Full Test Suite + Lint

**Step 1: Run backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS

**Step 2: Run frontend tests**

Run: `cd frontend && bun test`
Expected: All tests PASS

**Step 3: Run linter**

Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
Expected: No issues

**Step 4: Fix any issues found**

**Step 5: Final commit if any fixes**

```bash
git add -A
git commit -m "chore: fix lint issues"
```

---

### Task 11: Update Memory + Design Doc

**Files:**
- Modify: `/Users/morgandam/.claude/projects/-Users-morgandam-Documents-repos-nelson/memory/MEMORY.md`

Update MEMORY.md to reflect:
- Milestone 4 status
- New tables (default_models, user_custom_models)
- New API endpoints
- Updated model count (13 default models)

**Step 1: Commit**

```bash
git add docs/
git commit -m "docs: mark Milestone 4 as done"
```
