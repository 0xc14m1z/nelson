# Milestone 3 — API Keys + Model Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to store encrypted API keys, browse providers/models, configure default models and round preferences, and resolve which key to use for a given model.

**Architecture:** Four backend modules (keys, catalog, users, agent/model_registry) plus one frontend settings page. Keys are Fernet-encrypted at rest. Validation calls each provider's list-models endpoint. Model registry resolves user+model to the correct API key and base URL (own key → OpenRouter fallback).

**Tech Stack:** FastAPI, SQLAlchemy async, Fernet (cryptography), httpx, Mantine UI, TanStack Query (not yet installed — we'll add it).

**Design doc:** `docs/plans/2026-03-06-milestone-3-keys-config-design.md`

---

### Task 1: API Key DB Model + Migration

**Files:**
- Create: `backend/app/models/api_key.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<auto>_add_api_keys_and_user_default_models.py`

**Step 1: Create the ORM model**

Create `backend/app/models/api_key.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ApiKey(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider_id", name="uq_user_provider_key"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    provider: Mapped["Provider"] = relationship()  # noqa: F821, UP037
```

**Step 2: Add UserDefaultModel join table to `backend/app/models/user.py`**

Add below the `UserSettings` class:

```python
from sqlalchemy import Column, ForeignKey, Table
# (add at module level, using Core Table for join table — no ORM class needed)

user_default_models = Table(
    "user_default_models",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("llm_model_id", ForeignKey("llm_models.id", ondelete="CASCADE"), primary_key=True),
)
```

**Step 3: Update `backend/app/models/__init__.py`**

Add `ApiKey` and `user_default_models` to the imports and `__all__`.

**Step 4: Generate Alembic migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "add api_keys and user_default_models"`

Verify the generated migration creates `api_keys` table with all columns and `user_default_models` join table.

**Step 5: Write test for migration**

Create `backend/tests/test_api_key_model.py`:

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import ApiKey, Provider


@pytest.mark.asyncio
async def test_api_key_create_and_read():
    async with AsyncSession(engine) as session:
        # Get a provider
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        key = ApiKey(
            user_id=uuid.uuid4(),  # no FK check needed for this test pattern
            provider_id=provider.id,
            encrypted_key=b"fake-encrypted-data",
            is_valid=True,
        )
        session.add(key)
        await session.flush()

        result = await session.execute(select(ApiKey).where(ApiKey.id == key.id))
        saved = result.scalar_one()
        assert saved.encrypted_key == b"fake-encrypted-data"
        assert saved.is_valid is True
        assert saved.provider_id == provider.id
        await session.rollback()
```

**Step 6: Run test**

Run: `cd backend && uv run pytest tests/test_api_key_model.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/models/api_key.py backend/app/models/user.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_api_key_model.py
git commit -m "feat: add api_keys table and user_default_models join table"
```

---

### Task 2: Fernet Encryption Helpers

**Files:**
- Create: `backend/app/keys/encryption.py`
- Test: `backend/tests/test_encryption.py`

**Step 1: Write the failing test**

Create `backend/tests/test_encryption.py`:

```python
import pytest

from app.keys.encryption import decrypt_api_key, encrypt_api_key


def test_encrypt_decrypt_roundtrip():
    original = "sk-test-key-12345"
    encrypted = encrypt_api_key(original)
    assert isinstance(encrypted, bytes)
    assert encrypted != original.encode()  # not plaintext
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original


def test_encrypt_produces_different_ciphertexts():
    """Fernet includes a timestamp, so same plaintext → different ciphertext each time."""
    key = "sk-another-key"
    e1 = encrypt_api_key(key)
    e2 = encrypt_api_key(key)
    assert e1 != e2


def test_decrypt_invalid_data():
    with pytest.raises(Exception):
        decrypt_api_key(b"not-valid-fernet-data")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_encryption.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

**Step 3: Write implementation**

Create `backend/app/keys/encryption.py`:

```python
from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.fernet_key.encode())


def encrypt_api_key(raw_key: str) -> bytes:
    return _fernet.encrypt(raw_key.encode())


def decrypt_api_key(encrypted_key: bytes) -> bytes:
    return _fernet.decrypt(encrypted_key).decode()
```

Note: `settings.fernet_key` must be a valid Fernet key (base64-encoded 32 bytes). The test `.env` already has one from CI setup: `2lJYlIPWSL4O741w7QECrV46aeCY01t4zl2AwlVWNyI=`. The current default `"change-me-in-production"` is NOT a valid Fernet key. Update the `.env` or `config.py` default to the CI key for local dev.

**Step 4: Fix the Fernet key default in config**

In `backend/app/config.py`, change the fernet_key default:
```python
fernet_key: str = "2lJYlIPWSL4O741w7QECrV46aeCY01t4zl2AwlVWNyI="
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_encryption.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/keys/encryption.py backend/tests/test_encryption.py backend/app/config.py
git commit -m "feat: add Fernet encryption helpers for API keys"
```

---

### Task 3: Key Validation Service

**Files:**
- Create: `backend/app/keys/validation.py`
- Test: `backend/tests/test_key_validation.py`

**Step 1: Write the failing test**

Create `backend/tests/test_key_validation.py`:

```python
import pytest

from app.keys.validation import get_validation_config


def test_openai_validation_config():
    config = get_validation_config("openai", "https://api.openai.com/v1")
    assert config.url == "https://api.openai.com/v1/models"
    assert config.headers["Authorization"] == "Bearer {key}"


def test_anthropic_validation_config():
    config = get_validation_config("anthropic", "https://api.anthropic.com")
    assert config.url == "https://api.anthropic.com/v1/models"
    assert config.headers["x-api-key"] == "{key}"
    assert "anthropic-version" in config.headers


def test_google_validation_config():
    config = get_validation_config("google", "https://generativelanguage.googleapis.com/v1beta")
    assert "key={key}" in config.url


def test_unknown_provider_uses_bearer():
    config = get_validation_config("some-new-provider", "https://api.example.com/v1")
    assert config.url == "https://api.example.com/v1/models"
    assert config.headers["Authorization"] == "Bearer {key}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_key_validation.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/app/keys/validation.py`:

```python
from dataclasses import dataclass

import httpx


@dataclass
class ValidationConfig:
    url: str
    headers: dict[str, str]


def get_validation_config(provider_slug: str, base_url: str) -> ValidationConfig:
    """Return the URL and headers template for validating a key against a provider."""
    if provider_slug == "anthropic":
        return ValidationConfig(
            url=f"{base_url}/v1/models",
            headers={"x-api-key": "{key}", "anthropic-version": "2023-06-01"},
        )
    if provider_slug == "google":
        return ValidationConfig(
            url=f"{base_url}/models?key={{key}}",
            headers={},
        )
    # OpenAI, Mistral, OpenRouter, and any future provider: Bearer token + /models
    return ValidationConfig(
        url=f"{base_url}/models",
        headers={"Authorization": "Bearer {key}"},
    )


async def validate_api_key(provider_slug: str, base_url: str, raw_key: str) -> tuple[bool, str | None]:
    """Validate an API key by calling the provider's list-models endpoint.

    Returns (is_valid, error_message).
    """
    config = get_validation_config(provider_slug, base_url)
    url = config.url.replace("{key}", raw_key)
    headers = {k: v.replace("{key}", raw_key) for k, v in config.headers.items()}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (200, 201):
                return True, None
            if resp.status_code in (401, 403):
                return False, "Invalid API key"
            return False, f"Unexpected status {resp.status_code}"
    except httpx.TimeoutException:
        return False, "Validation request timed out"
    except httpx.RequestError as e:
        return False, f"Connection error: {e}"
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_key_validation.py -v`
Expected: PASS (the config tests don't make HTTP calls)

**Step 5: Commit**

```bash
git add backend/app/keys/validation.py backend/tests/test_key_validation.py
git commit -m "feat: add API key validation with provider-specific config"
```

---

### Task 4: Keys Schemas

**Files:**
- Create: `backend/app/keys/schemas.py`

**Step 1: Create schemas**

Create `backend/app/keys/schemas.py`:

```python
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
```

**Step 2: Commit**

```bash
git add backend/app/keys/schemas.py
git commit -m "feat: add API key request/response schemas"
```

---

### Task 5: Keys Service

**Files:**
- Create: `backend/app/keys/service.py`
- Test: `backend/tests/test_keys_service.py`

**Step 1: Write the failing test**

Create `backend/tests/test_keys_service.py`:

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.keys.encryption import decrypt_api_key
from app.keys.service import delete_key, get_decrypted_key, list_keys, store_key
from app.models import ApiKey, Provider, User, UserSettings


async def _create_test_user(session: AsyncSession) -> User:
    user = User(email=f"test-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_store_key_encrypts_and_saves():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        key_record = await store_key(
            user_id=user.id,
            provider_id=provider.id,
            raw_key="sk-test-12345",
            db=session,
            skip_validation=True,
        )

        assert key_record.is_valid is True
        assert key_record.provider_id == provider.id
        # Verify it's actually encrypted
        decrypted = decrypt_api_key(key_record.encrypted_key)
        assert decrypted == "sk-test-12345"
        await session.rollback()


@pytest.mark.asyncio
async def test_store_key_upserts_on_duplicate():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-first", session, skip_validation=True)
        await store_key(user.id, provider.id, "sk-second", session, skip_validation=True)

        # Should have only one key for this provider
        keys = await session.execute(
            select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.provider_id == provider.id)
        )
        all_keys = keys.scalars().all()
        assert len(all_keys) == 1
        assert decrypt_api_key(all_keys[0].encrypted_key) == "sk-second"
        await session.rollback()


@pytest.mark.asyncio
async def test_list_keys_returns_masked():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-test-secret-key", session, skip_validation=True)
        keys = await list_keys(user.id, session)

        assert len(keys) == 1
        assert keys[0].masked_key == "****-key"
        assert keys[0].provider_slug == "openai"


@pytest.mark.asyncio
async def test_delete_key():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-to-delete", session, skip_validation=True)
        deleted = await delete_key(user.id, provider.id, session)
        assert deleted is True

        keys = await list_keys(user.id, session)
        assert len(keys) == 0
        await session.rollback()


@pytest.mark.asyncio
async def test_get_decrypted_key():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-my-secret", session, skip_validation=True)
        decrypted = await get_decrypted_key(user.id, provider.id, session)
        assert decrypted == "sk-my-secret"
        await session.rollback()


@pytest.mark.asyncio
async def test_get_decrypted_key_not_found():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        decrypted = await get_decrypted_key(user.id, uuid.uuid4(), session)
        assert decrypted is None
        await session.rollback()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_keys_service.py -v`
Expected: FAIL (ImportError)

**Step 3: Write implementation**

Create `backend/app/keys/service.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keys.encryption import decrypt_api_key, encrypt_api_key
from app.keys.validation import validate_api_key
from app.models import ApiKey, Provider


class InvalidKeyError(Exception):
    def __init__(self, message: str = "Invalid API key"):
        self.message = message
        super().__init__(self.message)


async def store_key(
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    raw_key: str,
    db: AsyncSession,
    *,
    skip_validation: bool = False,
) -> ApiKey:
    """Encrypt and store (or update) an API key. Validates first unless skip_validation=True."""
    is_valid = True
    validated_at = None

    if not skip_validation:
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None:
            raise ValueError("Provider not found")

        is_valid, error = await validate_api_key(provider.slug, provider.base_url, raw_key)
        if not is_valid:
            raise InvalidKeyError(error or "Invalid API key")
        validated_at = datetime.now(UTC)

    encrypted = encrypt_api_key(raw_key)

    # Upsert: check for existing key for this user+provider
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_key = encrypted
        existing.is_valid = is_valid
        existing.validated_at = validated_at or existing.validated_at
        await db.flush()
        return existing

    key = ApiKey(
        user_id=user_id,
        provider_id=provider_id,
        encrypted_key=encrypted,
        is_valid=is_valid,
        validated_at=validated_at,
    )
    db.add(key)
    await db.flush()
    return key


async def list_keys(user_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Return all keys for a user with masked display and provider info."""
    result = await db.execute(
        select(ApiKey)
        .options(joinedload(ApiKey.provider))
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at)
    )
    keys = result.scalars().all()

    return [
        type(
            "MaskedKey",
            (),
            {
                "id": key.id,
                "provider_id": key.provider_id,
                "provider_slug": key.provider.slug,
                "provider_display_name": key.provider.display_name,
                "masked_key": _mask_key(decrypt_api_key(key.encrypted_key)),
                "is_valid": key.is_valid,
                "validated_at": key.validated_at,
                "created_at": key.created_at,
            },
        )
        for key in keys
    ]


async def delete_key(user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession) -> bool:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return False
    await db.delete(key)
    await db.flush()
    return True


async def get_decrypted_key(
    user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession
) -> str | None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return None
    return decrypt_api_key(key.encrypted_key)


async def validate_existing_key(
    user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession
) -> tuple[bool, str | None]:
    """Re-validate a stored key by calling the provider API."""
    result = await db.execute(
        select(ApiKey)
        .options(joinedload(ApiKey.provider))
        .where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return False, "No key stored for this provider"

    raw_key = decrypt_api_key(key.encrypted_key)
    is_valid, error = await validate_api_key(key.provider.slug, key.provider.base_url, raw_key)
    key.is_valid = is_valid
    key.validated_at = datetime.now(UTC)
    await db.flush()
    return is_valid, error


def _mask_key(raw_key: str) -> str:
    """Mask a key, showing only the last 4 characters."""
    if len(raw_key) <= 4:
        return "****"
    return f"****{raw_key[-4:]}"
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_keys_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/keys/service.py backend/tests/test_keys_service.py
git commit -m "feat: add keys service with store, list, delete, validate"
```

---

### Task 6: Keys Router

**Files:**
- Create: `backend/app/keys/router.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_keys_router.py`

**Step 1: Write the failing test**

Create `backend/tests/test_keys_router.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.main import app
from app.models import Provider
from tests.conftest import extract_token_from_mailpit


async def _get_auth_token(client: AsyncClient) -> str:
    """Create a user via magic link and return an access token."""
    email = "keys-test@example.com"
    await client.post("/api/auth/magic-link", json={"email": email})
    token = await extract_token_from_mailpit(email)
    resp = await client.post("/api/auth/verify", json={"email": email, "token": token})
    return resp.json()["access_token"]


async def _get_provider_id(slug: str) -> str:
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Provider).where(Provider.slug == slug))
        return str(result.scalar_one().id)


@pytest.mark.asyncio
async def test_list_keys_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client)
        resp = await client.get(
            "/api/keys", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_store_and_list_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client)
        provider_id = await _get_provider_id("openai")
        headers = {"Authorization": f"Bearer {token}"}

        # Store (skip_validation via query param for tests — or we test with real key)
        resp = await client.post(
            "/api/keys",
            json={"provider_id": provider_id, "api_key": "sk-test-key-12345"},
            headers=headers,
            params={"skip_validation": "true"},
        )
        assert resp.status_code == 201

        # List
        resp = await client.get("/api/keys", headers=headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1
        key = next(k for k in keys if k["provider_slug"] == "openai")
        assert key["masked_key"] == "****2345"
        assert key["is_valid"] is True


@pytest.mark.asyncio
async def test_delete_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client)
        provider_id = await _get_provider_id("mistral")
        headers = {"Authorization": f"Bearer {token}"}

        # Store first
        await client.post(
            "/api/keys",
            json={"provider_id": provider_id, "api_key": "sk-mistral-key"},
            headers=headers,
            params={"skip_validation": "true"},
        )

        # Delete
        resp = await client.delete(f"/api/keys/{provider_id}", headers=headers)
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get("/api/keys", headers=headers)
        keys = resp.json()
        assert not any(k["provider_slug"] == "mistral" for k in keys)


@pytest.mark.asyncio
async def test_unauthenticated_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/keys")
        assert resp.status_code == 403  # HTTPBearer returns 403 when no credentials
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_keys_router.py -v`
Expected: FAIL (404 — router not registered yet)

**Step 3: Write implementation**

Create `backend/app/keys/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.keys.schemas import ApiKeyResponse, StoreKeyRequest, ValidateKeyResponse
from app.keys.service import (
    InvalidKeyError,
    delete_key,
    list_keys,
    store_key,
    validate_existing_key,
)
from app.models import User

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.get("", response_model=list[ApiKeyResponse])
async def get_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_keys(current_user.id, db)


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_key(
    body: StoreKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip_validation: bool = Query(False),
):
    try:
        key = await store_key(
            current_user.id, body.provider_id, body.api_key, db, skip_validation=skip_validation
        )
        await db.commit()
        # Re-fetch with provider loaded for response
        keys = await list_keys(current_user.id, db)
        return next(k for k in keys if k.provider_id == body.provider_id)
    except InvalidKeyError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{provider_id}", status_code=204)
async def remove_key(
    provider_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_key(current_user.id, provider_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="No key found for this provider")
    await db.commit()


@router.post("/{provider_id}/validate", response_model=ValidateKeyResponse)
async def validate_key(
    provider_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_valid, error = await validate_existing_key(current_user.id, provider_id, db)
    await db.commit()
    return ValidateKeyResponse(is_valid=is_valid, error=error)
```

**Step 4: Register router in `backend/app/main.py`**

Add after the auth router import and include:

```python
from app.keys.router import router as keys_router
# ...
app.include_router(keys_router)
```

**Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_keys_router.py -v`
Expected: PASS

**Step 6: Run all tests to check no regressions**

Run: `cd backend && uv run pytest -v`
Expected: All pass

**Step 7: Commit**

```bash
git add backend/app/keys/router.py backend/app/main.py backend/tests/test_keys_router.py
git commit -m "feat: add API keys CRUD endpoints"
```

---

### Task 7: Catalog Router (Providers + Models)

**Files:**
- Create: `backend/app/catalog/__init__.py`
- Create: `backend/app/catalog/router.py`
- Create: `backend/app/catalog/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_catalog_router.py`

**Step 1: Write the failing test**

Create `backend/tests/test_catalog_router.py`:

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
        assert len(models) == 11


@pytest.mark.asyncio
async def test_list_models_filtered_by_provider():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get OpenAI provider ID first
        providers_resp = await client.get("/api/providers")
        openai = next(p for p in providers_resp.json() if p["slug"] == "openai")

        resp = await client.get(f"/api/models?provider_id={openai['id']}")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) == 4  # gpt-4o, gpt-4o-mini, o1, o1-mini
        assert all(m["provider_slug"] == "openai" for m in models)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_catalog_router.py -v`
Expected: FAIL (404)

**Step 3: Create schemas**

Create `backend/app/catalog/__init__.py` (empty file).

Create `backend/app/catalog/schemas.py`:

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
    input_price_per_mtok: Decimal
    output_price_per_mtok: Decimal
    is_active: bool
    context_window: int

    model_config = {"from_attributes": True}
```

**Step 4: Create router**

Create `backend/app/catalog/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.catalog.schemas import ModelResponse, ProviderResponse
from app.database import get_db
from app.models import LLMModel, Provider

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider).where(Provider.is_active.is_(True)).order_by(Provider.display_name)
    )
    return result.scalars().all()


@router.get("/models", response_model=list[ModelResponse])
async def list_models(
    provider_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(LLMModel)
        .options(joinedload(LLMModel.provider))
        .where(LLMModel.is_active.is_(True))
    )
    if provider_id:
        query = query.where(LLMModel.provider_id == provider_id)
    query = query.order_by(LLMModel.display_name)
    result = await db.execute(query)
    models = result.scalars().all()

    return [
        ModelResponse(
            id=m.id,
            provider_id=m.provider_id,
            provider_slug=m.provider.slug,
            slug=m.slug,
            display_name=m.display_name,
            input_price_per_mtok=m.input_price_per_mtok,
            output_price_per_mtok=m.output_price_per_mtok,
            is_active=m.is_active,
            context_window=m.context_window,
        )
        for m in models
    ]
```

**Step 5: Register in `backend/app/main.py`**

```python
from app.catalog.router import router as catalog_router
# ...
app.include_router(catalog_router)
```

**Step 6: Run tests**

Run: `cd backend && uv run pytest tests/test_catalog_router.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/catalog/ backend/tests/test_catalog_router.py backend/app/main.py
git commit -m "feat: add providers and models catalog endpoints"
```

---

### Task 8: Users Router (Profile + Settings)

**Files:**
- Create: `backend/app/users/router.py`
- Create: `backend/app/users/service.py`
- Create: `backend/app/users/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_users_router.py`

**Step 1: Write the failing test**

Create `backend/tests/test_users_router.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import extract_token_from_mailpit


async def _get_auth_token(client: AsyncClient, email: str = "users-test@example.com") -> str:
    await client.post("/api/auth/magic-link", json={"email": email})
    token = await extract_token_from_mailpit(email)
    resp = await client.post("/api/auth/verify", json={"email": email, "token": token})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client)
        resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "users-test@example.com"
        assert data["billing_mode"] == "own_keys"


@pytest.mark.asyncio
async def test_update_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "update-profile@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.put(
            "/api/users/me",
            json={"display_name": "Test User"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Test User"


@pytest.mark.asyncio
async def test_get_settings_default():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "settings-default@example.com")
        resp = await client.get(
            "/api/users/me/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_rounds"] is None
        assert data["default_model_ids"] == []


@pytest.mark.asyncio
async def test_update_settings_with_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "settings-models@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Get model IDs from catalog
        models_resp = await client.get("/api/models")
        model_ids = [m["id"] for m in models_resp.json()[:3]]

        # Update
        resp = await client.put(
            "/api/users/me/settings",
            json={"max_rounds": 5, "default_model_ids": model_ids},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["max_rounds"] == 5
        assert set(data["default_model_ids"]) == set(model_ids)


@pytest.mark.asyncio
async def test_update_settings_invalid_model_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "settings-invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.put(
            "/api/users/me/settings",
            json={"default_model_ids": ["00000000-0000-0000-0000-000000000099"]},
            headers=headers,
        )
        assert resp.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_users_router.py -v`
Expected: FAIL

**Step 3: Create schemas**

Create `backend/app/users/schemas.py`:

```python
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
```

**Step 4: Create service**

Create `backend/app/users/service.py`:

```python
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMModel, User, UserSettings
from app.models.user import user_default_models


async def get_settings(user_id: uuid.UUID, db: AsyncSession) -> dict:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()

    model_ids_result = await db.execute(
        select(user_default_models.c.llm_model_id).where(
            user_default_models.c.user_id == user_id
        )
    )
    model_ids = [row[0] for row in model_ids_result.all()]

    return {
        "max_rounds": settings.max_rounds if settings else None,
        "default_model_ids": model_ids,
    }


async def update_settings(
    user_id: uuid.UUID,
    max_rounds: int | None,
    default_model_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict:
    # Validate model IDs exist and are active
    if default_model_ids:
        result = await db.execute(
            select(LLMModel.id).where(
                LLMModel.id.in_(default_model_ids),
                LLMModel.is_active.is_(True),
            )
        )
        valid_ids = {row[0] for row in result.all()}
        invalid = set(default_model_ids) - valid_ids
        if invalid:
            raise ValueError(f"Invalid or inactive model IDs: {invalid}")

    # Upsert user_settings
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings:
        settings.max_rounds = max_rounds
    else:
        settings = UserSettings(user_id=user_id, max_rounds=max_rounds)
        db.add(settings)
    await db.flush()

    # Sync default models: delete all, re-insert
    await db.execute(
        delete(user_default_models).where(user_default_models.c.user_id == user_id)
    )
    if default_model_ids:
        await db.execute(
            user_default_models.insert(),
            [{"user_id": user_id, "llm_model_id": mid} for mid in default_model_ids],
        )
    await db.flush()

    return {
        "max_rounds": max_rounds,
        "default_model_ids": default_model_ids,
    }
```

**Step 5: Create router**

Create `backend/app/users/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.users.schemas import (
    ProfileResponse,
    SettingsResponse,
    UpdateProfileRequest,
    UpdateSettingsRequest,
)
from app.users.service import get_settings, update_settings

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=ProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.billing_mode is not None:
        current_user.billing_mode = body.billing_mode
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/settings", response_model=SettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_settings(current_user.id, db)


@router.put("/me/settings", response_model=SettingsResponse)
async def update_user_settings(
    body: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await update_settings(
            current_user.id, body.max_rounds, body.default_model_ids, db
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

**Step 6: Register in `backend/app/main.py`**

```python
from app.users.router import router as users_router
# ...
app.include_router(users_router)
```

**Step 7: Run tests**

Run: `cd backend && uv run pytest tests/test_users_router.py -v`
Expected: PASS

**Step 8: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All pass

**Step 9: Commit**

```bash
git add backend/app/users/ backend/tests/test_users_router.py backend/app/main.py
git commit -m "feat: add user profile and settings endpoints"
```

---

### Task 9: Model Registry

**Files:**
- Create: `backend/app/agent/model_registry.py`
- Test: `backend/tests/test_model_registry.py`

**Step 1: Write the failing test**

Create `backend/tests/test_model_registry.py`:

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.database import engine
from app.keys.service import store_key
from app.models import LLMModel, Provider, User, UserSettings


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"registry-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


async def _get_model(session: AsyncSession, slug: str) -> LLMModel:
    result = await session.execute(
        select(LLMModel).where(LLMModel.slug == slug)
    )
    return result.scalar_one()


async def _get_provider(session: AsyncSession, slug: str) -> Provider:
    result = await session.execute(
        select(Provider).where(Provider.slug == slug)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_resolve_with_direct_key():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        provider = await _get_provider(session, "openai")
        model = await _get_model(session, "gpt-4o")

        await store_key(user.id, provider.id, "sk-direct-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.api_key == "sk-direct-key"
        assert resolved.base_url == "https://api.openai.com/v1"
        assert resolved.model_slug == "gpt-4o"
        assert resolved.provider_slug == "openai"
        assert resolved.via_openrouter is False
        await session.rollback()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_openrouter():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        model = await _get_model(session, "gpt-4o")

        # No OpenAI key, but has OpenRouter key
        await store_key(user.id, openrouter.id, "sk-or-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.api_key == "sk-or-key"
        assert resolved.base_url == "https://openrouter.ai/api/v1"
        assert resolved.model_slug == "openai/gpt-4o"
        assert resolved.via_openrouter is True
        await session.rollback()


@pytest.mark.asyncio
async def test_resolve_openrouter_native_model():
    """OpenRouter-native models don't get slug prefix."""
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")

        # Create a hypothetical OpenRouter-native model for testing
        # In reality, the seed data doesn't have OR-native models yet,
        # so we test with an OpenAI model accessed via direct OR key
        model = await _get_model(session, "gpt-4o")

        # User has OpenAI key — should use direct, not OR
        openai = await _get_provider(session, "openai")
        await store_key(user.id, openai.id, "sk-openai-direct", session, skip_validation=True)
        await store_key(user.id, openrouter.id, "sk-or-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        # Direct key takes priority
        assert resolved.via_openrouter is False
        assert resolved.api_key == "sk-openai-direct"
        await session.rollback()


@pytest.mark.asyncio
async def test_resolve_no_key_raises():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        model = await _get_model(session, "gpt-4o")

        with pytest.raises(NoKeyAvailableError):
            await resolve_model(user.id, model, session)
        await session.rollback()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_model_registry.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/app/agent/model_registry.py`:

```python
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keys.service import get_decrypted_key
from app.models import LLMModel, Provider


class NoKeyAvailableError(Exception):
    def __init__(self, model_slug: str):
        self.model_slug = model_slug
        super().__init__(f"No API key available for model '{model_slug}'")


@dataclass
class ResolvedModel:
    api_key: str
    base_url: str
    model_slug: str
    provider_slug: str
    via_openrouter: bool


async def resolve_model(
    user_id: uuid.UUID,
    llm_model: LLMModel,
    db: AsyncSession,
) -> ResolvedModel:
    """Resolve which API key and base URL to use for a given model.

    Resolution order:
    1. User's own key for the model's provider
    2. User's OpenRouter key (with slug translation)
    3. Raise NoKeyAvailableError
    """
    # Ensure provider is loaded
    if not llm_model.provider:
        result = await db.execute(
            select(LLMModel).options(joinedload(LLMModel.provider)).where(LLMModel.id == llm_model.id)
        )
        llm_model = result.scalar_one()

    provider = llm_model.provider

    # Step 1: Try user's own key for this provider
    direct_key = await get_decrypted_key(user_id, provider.id, db)
    if direct_key:
        return ResolvedModel(
            api_key=direct_key,
            base_url=provider.base_url,
            model_slug=llm_model.slug,
            provider_slug=provider.slug,
            via_openrouter=False,
        )

    # Step 2: Try OpenRouter fallback (skip if model is already OpenRouter-native)
    if provider.slug != "openrouter":
        or_provider = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
        openrouter = or_provider.scalar_one_or_none()
        if openrouter:
            or_key = await get_decrypted_key(user_id, openrouter.id, db)
            if or_key:
                return ResolvedModel(
                    api_key=or_key,
                    base_url=openrouter.base_url,
                    model_slug=f"{provider.slug}/{llm_model.slug}",
                    provider_slug="openrouter",
                    via_openrouter=True,
                )

    # Step 3: No key available
    raise NoKeyAvailableError(llm_model.slug)
```

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_model_registry.py -v`
Expected: PASS

**Step 5: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/app/agent/model_registry.py backend/tests/test_model_registry.py
git commit -m "feat: add model registry with key resolution and OpenRouter fallback"
```

---

### Task 10: Install TanStack Query in Frontend

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/query-provider.tsx`
- Modify: `frontend/src/app/layout.tsx` (or root providers)

**Step 1: Install TanStack Query**

Run: `cd frontend && bun add @tanstack/react-query`

**Step 2: Create query provider**

Create `frontend/src/lib/query-provider.tsx`:

```tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

**Step 3: Add QueryProvider to root layout**

In `frontend/src/app/layout.tsx`, wrap children with `<QueryProvider>` (inside `MantineProvider`, outside `AuthProvider` or alongside it).

**Step 4: Commit**

```bash
git add frontend/package.json frontend/bun.lock frontend/src/lib/query-provider.tsx frontend/src/app/layout.tsx
git commit -m "feat: add TanStack Query provider"
```

---

### Task 11: Frontend API Hooks

**Files:**
- Create: `frontend/src/lib/hooks.ts`

**Step 1: Create hooks**

Create `frontend/src/lib/hooks.ts`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

// Types
export interface Provider {
  id: string;
  slug: string;
  display_name: string;
  base_url: string;
  is_active: boolean;
}

export interface Model {
  id: string;
  provider_id: string;
  provider_slug: string;
  slug: string;
  display_name: string;
  input_price_per_mtok: string;
  output_price_per_mtok: string;
  is_active: boolean;
  context_window: number;
}

export interface ApiKey {
  id: string;
  provider_id: string;
  provider_slug: string;
  provider_display_name: string;
  masked_key: string;
  is_valid: boolean;
  validated_at: string | null;
  created_at: string;
}

export interface UserSettings {
  max_rounds: number | null;
  default_model_ids: string[];
}

// Queries
export function useProviders() {
  return useQuery<Provider[]>({
    queryKey: ["providers"],
    queryFn: async () => {
      const resp = await apiFetch("/api/providers");
      if (!resp.ok) throw new Error("Failed to fetch providers");
      return resp.json();
    },
  });
}

export function useModels(providerId?: string) {
  return useQuery<Model[]>({
    queryKey: ["models", providerId],
    queryFn: async () => {
      const url = providerId
        ? `/api/models?provider_id=${providerId}`
        : "/api/models";
      const resp = await apiFetch(url);
      if (!resp.ok) throw new Error("Failed to fetch models");
      return resp.json();
    },
  });
}

export function useApiKeys() {
  return useQuery<ApiKey[]>({
    queryKey: ["apiKeys"],
    queryFn: async () => {
      const resp = await apiFetch("/api/keys");
      if (!resp.ok) throw new Error("Failed to fetch API keys");
      return resp.json();
    },
  });
}

export function useUserSettings() {
  return useQuery<UserSettings>({
    queryKey: ["userSettings"],
    queryFn: async () => {
      const resp = await apiFetch("/api/users/me/settings");
      if (!resp.ok) throw new Error("Failed to fetch settings");
      return resp.json();
    },
  });
}

// Mutations
export function useStoreKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      providerId,
      apiKey,
    }: {
      providerId: string;
      apiKey: string;
    }) => {
      const resp = await apiFetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider_id: providerId, api_key: apiKey }),
      });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "Failed to store key");
      }
      return resp.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useDeleteKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const resp = await apiFetch(`/api/keys/${providerId}`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error("Failed to delete key");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useValidateKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const resp = await apiFetch(`/api/keys/${providerId}/validate`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error("Failed to validate key");
      return resp.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (settings: {
      max_rounds?: number | null;
      default_model_ids?: string[];
    }) => {
      const resp = await apiFetch("/api/users/me/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!resp.ok) throw new Error("Failed to update settings");
      return resp.json();
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["userSettings"] }),
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/hooks.ts
git commit -m "feat: add TanStack Query hooks for keys, models, settings"
```

---

### Task 12: Settings Page — API Keys Tab

**Files:**
- Create: `frontend/src/app/(protected)/settings/page.tsx`

**Step 1: Create the settings page**

Use the `frontend-design` skill for this task. The page needs:

- Mantine `Tabs` with three tabs: API Keys, Default Models, Preferences
- **API Keys tab**: List all providers. For each, show status badge (stored/not stored, valid/invalid), masked key, and action buttons (Add/Update modal, Test, Delete with confirmation).
- Use `@mantine/notifications` for success/error feedback.
- Use `useProviders()`, `useApiKeys()`, `useStoreKey()`, `useDeleteKey()`, `useValidateKey()` hooks.
- Mantine modal for key input (TextInput + submit).

Create `frontend/src/app/(protected)/settings/page.tsx` with the full three-tab structure. Implement the API Keys tab fully; the other two tabs can be placeholder content initially (they'll be filled in the next tasks).

**Step 2: Add Settings link to dashboard**

In `frontend/src/app/(protected)/dashboard/page.tsx`, add a "Settings" link/button that navigates to `/settings`.

**Step 3: Run frontend**

Run: `cd frontend && bun run build`
Expected: Builds without errors

**Step 4: Commit**

```bash
git add frontend/src/app/\(protected\)/settings/ frontend/src/app/\(protected\)/dashboard/page.tsx
git commit -m "feat: add settings page with API keys tab"
```

---

### Task 13: Settings Page — Default Models + Preferences Tabs

**Files:**
- Modify: `frontend/src/app/(protected)/settings/page.tsx`

**Step 1: Implement Default Models tab**

- Use `useModels()`, `useApiKeys()`, `useUserSettings()`, `useUpdateSettings()`
- Group models by provider using Mantine `Checkbox.Group` or similar
- Only show models where user has a key for that provider (or OpenRouter key)
- Save button calls mutation

**Step 2: Implement Preferences tab**

- Toggle between "Until consensus" (null) and specific round count
- Mantine `Switch` + `NumberInput` (range 2-20, disabled when switch is off)
- Save button calls mutation

**Step 3: Build and verify**

Run: `cd frontend && bun run build`
Expected: Builds without errors

**Step 4: Commit**

```bash
git add frontend/src/app/\(protected\)/settings/page.tsx
git commit -m "feat: add default models and preferences tabs to settings"
```

---

### Task 14: Frontend Tests

**Files:**
- Create: `frontend/src/app/(protected)/settings/__tests__/page.test.tsx`

**Step 1: Write tests**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the hooks
vi.mock("../../../../lib/hooks", () => ({
  useProviders: () => ({
    data: [
      { id: "1", slug: "openai", display_name: "OpenAI", is_active: true },
      { id: "2", slug: "anthropic", display_name: "Anthropic", is_active: true },
    ],
    isLoading: false,
  }),
  useApiKeys: () => ({
    data: [
      {
        id: "k1",
        provider_id: "1",
        provider_slug: "openai",
        provider_display_name: "OpenAI",
        masked_key: "****2345",
        is_valid: true,
        validated_at: "2026-01-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
    isLoading: false,
  }),
  useModels: () => ({
    data: [
      { id: "m1", provider_id: "1", provider_slug: "openai", slug: "gpt-4o", display_name: "GPT-4o" },
    ],
    isLoading: false,
  }),
  useUserSettings: () => ({
    data: { max_rounds: null, default_model_ids: [] },
    isLoading: false,
  }),
  useStoreKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useValidateKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSettings: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// Mock auth context
vi.mock("../../../../lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "test@example.com", display_name: null, billing_mode: "own_keys" },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

import SettingsPage from "../page";

// Wrap with MantineProvider for tests
import { MantineProvider } from "@mantine/core";

function renderWithMantine(ui: React.ReactElement) {
  return render(<MantineProvider>{ui}</MantineProvider>);
}

describe("Settings Page", () => {
  it("renders tabs", () => {
    renderWithMantine(<SettingsPage />);
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("Default Models")).toBeInTheDocument();
    expect(screen.getByText("Preferences")).toBeInTheDocument();
  });

  it("shows stored key as masked", () => {
    renderWithMantine(<SettingsPage />);
    expect(screen.getByText("****2345")).toBeInTheDocument();
  });

  it("shows provider without key", () => {
    renderWithMantine(<SettingsPage />);
    expect(screen.getByText("Anthropic")).toBeInTheDocument();
  });
});
```

**Step 2: Run tests**

Run: `cd frontend && bun run test`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/app/\(protected\)/settings/__tests__/
git commit -m "test: add settings page tests"
```

---

### Task 15: Lint + Full Test Pass + Final Commit

**Step 1: Run linter**

Run: `cd backend && uv run ruff check . --fix && uv run ruff format .`
Run: `cd frontend && bun run lint`

Fix any issues.

**Step 2: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All pass (should be ~50+ tests now)

**Step 3: Run all frontend tests**

Run: `cd frontend && bun run test`
Expected: All pass

**Step 4: Verify build**

Run: `cd frontend && bun run build`
Expected: Builds clean

**Step 5: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: lint fixes for milestone 3"
```

**Step 6: Update PLAN.md**

In `PLAN.md`, change Milestone 3 status from `TODO` to `DONE`.

```bash
git add PLAN.md
git commit -m "docs: mark Milestone 3 as done"
```
