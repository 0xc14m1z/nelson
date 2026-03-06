import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.main import app
from app.models import Provider
from tests.conftest import extract_token_from_mailpit


async def _get_auth_token(client: AsyncClient, email: str = "keys-test@example.com") -> str:
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
        token = await _get_auth_token(client, "keys-empty@example.com")
        resp = await client.get("/api/keys", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_store_and_list_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "keys-store@example.com")
        provider_id = await _get_provider_id("openai")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/keys",
            json={"provider_id": provider_id, "api_key": "sk-test-key-12345"},
            headers=headers,
            params={"skip_validation": "true"},
        )
        assert resp.status_code == 201

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
        token = await _get_auth_token(client, "keys-delete@example.com")
        provider_id = await _get_provider_id("mistral")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/keys",
            json={"provider_id": provider_id, "api_key": "sk-mistral-key"},
            headers=headers,
            params={"skip_validation": "true"},
        )

        resp = await client.delete(f"/api/keys/{provider_id}", headers=headers)
        assert resp.status_code == 204

        resp = await client.get("/api/keys", headers=headers)
        keys = resp.json()
        assert not any(k["provider_slug"] == "mistral" for k in keys)


@pytest.mark.asyncio
async def test_unauthenticated_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/keys")
        assert resp.status_code in (401, 403)
