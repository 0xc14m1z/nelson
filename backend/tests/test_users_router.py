import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import extract_token_from_mailpit


async def _get_auth_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/magic-link", json={"email": email})
    token = await extract_token_from_mailpit(email)
    resp = await client.post("/api/auth/verify", json={"email": email, "token": token})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_get_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "users-profile@example.com")
        resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "users-profile@example.com"
        assert data["billing_mode"] == "own_keys"


@pytest.mark.asyncio
async def test_update_profile():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "users-update@example.com")
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
        token = await _get_auth_token(client, "users-settings-default@example.com")
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
        token = await _get_auth_token(client, "users-settings-models@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        models_resp = await client.get("/api/models")
        model_ids = [m["id"] for m in models_resp.json()[:3]]

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
async def test_update_summarizer_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "users-summarizer@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Get a model ID from seed data
        models_resp = await client.get("/api/models")
        model_id = models_resp.json()[0]["id"]

        resp = await client.put(
            "/api/users/me/settings",
            json={"summarizer_model_id": model_id},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["summarizer_model_id"] == model_id

        # Verify it persists via GET
        get_resp = await client.get("/api/users/me/settings", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["summarizer_model_id"] == model_id


@pytest.mark.asyncio
async def test_update_settings_invalid_model_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "users-settings-invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.put(
            "/api/users/me/settings",
            json={"default_model_ids": ["00000000-0000-0000-0000-000000000099"]},
            headers=headers,
        )
        assert resp.status_code == 422
