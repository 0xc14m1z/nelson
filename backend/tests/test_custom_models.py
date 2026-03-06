import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import _create_access_token
from app.database import engine
from app.keys.encryption import encrypt_api_key
from app.main import app
from app.models import ApiKey, Provider, User


def _unique_email(prefix: str) -> str:
    """Generate a unique email to avoid conflicts across test runs."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


async def _setup_user_with_openrouter_key(
    email: str | None = None,
) -> tuple[str, uuid.UUID]:
    if email is None:
        email = _unique_email("cm")
    """Create a user and store an OpenRouter API key. Returns (jwt, user_id)."""
    async with AsyncSession(engine) as session:
        user = User(email=email)
        session.add(user)
        await session.flush()
        user_id = user.id

        # Get OpenRouter provider
        result = await session.execute(select(Provider).where(Provider.slug == "openrouter"))
        provider = result.scalar_one()

        # Store a fake API key
        api_key = ApiKey(
            user_id=user_id,
            provider_id=provider.id,
            encrypted_key=encrypt_api_key("sk-or-test-key-12345"),
            is_valid=True,
        )
        session.add(api_key)
        await session.commit()

    token = _create_access_token(str(user_id), email)
    return token, user_id


@pytest.mark.asyncio
async def test_add_custom_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token, _ = await _setup_user_with_openrouter_key(_unique_email("cm-add"))
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "test/model-1",
                "display_name": "Test Model 1",
                "model_type": "text",
                "input_price_per_mtok": "1.5",
                "output_price_per_mtok": "3.0",
                "context_window": 64000,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "test/model-1"
        assert data["display_name"] == "Test Model 1"
        assert data["context_window"] == 64000
        assert "id" in data


@pytest.mark.asyncio
async def test_add_duplicate_custom_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token, _ = await _setup_user_with_openrouter_key(_unique_email("cm-dup"))
        headers = {"Authorization": f"Bearer {token}"}

        body = {
            "model_slug": "test/dup-model",
            "display_name": "Dup Model",
        }

        resp = await client.post(
            "/api/users/me/custom-models",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 201

        resp = await client.post(
            "/api/users/me/custom-models",
            json=body,
            headers=headers,
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_custom_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token, _ = await _setup_user_with_openrouter_key(_unique_email("cm-list"))
        headers = {"Authorization": f"Bearer {token}"}

        # Add a model first
        await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "test/list-model",
                "display_name": "List Model",
            },
            headers=headers,
        )

        resp = await client.get(
            "/api/users/me/custom-models",
            headers=headers,
        )
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) >= 1
        slugs = [m["slug"] for m in models]
        assert "test/list-model" in slugs


@pytest.mark.asyncio
async def test_delete_custom_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token, _ = await _setup_user_with_openrouter_key(_unique_email("cm-del"))
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/users/me/custom-models",
            json={
                "model_slug": "test/del-model",
                "display_name": "Delete Model",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        model_id = resp.json()["id"]

        resp = await client.delete(
            f"/api/users/me/custom-models/{model_id}",
            headers=headers,
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(
            "/api/users/me/custom-models",
            headers=headers,
        )
        models = resp.json()
        assert not any(m["id"] == model_id for m in models)


@pytest.mark.asyncio
async def test_delete_nonexistent_custom_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token, _ = await _setup_user_with_openrouter_key(_unique_email("cm-del404"))
        headers = {"Authorization": f"Bearer {token}"}

        fake_id = str(uuid.uuid4())
        resp = await client.delete(
            f"/api/users/me/custom-models/{fake_id}",
            headers=headers,
        )
        assert resp.status_code == 404
