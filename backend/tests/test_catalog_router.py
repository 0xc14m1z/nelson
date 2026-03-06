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
        providers_resp = await client.get("/api/providers")
        openai = next(p for p in providers_resp.json() if p["slug"] == "openai")

        resp = await client.get(f"/api/models?provider_id={openai['id']}")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) == 4
        assert all(m["provider_slug"] == "openai" for m in models)
