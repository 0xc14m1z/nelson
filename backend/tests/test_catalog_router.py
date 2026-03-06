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
        assert len(providers) == 6
        slugs = {p["slug"] for p in providers}
        assert slugs == {"openai", "anthropic", "google", "mistral", "openrouter", "xai"}


@pytest.mark.asyncio
async def test_list_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/models")
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) >= 14


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
        assert resp.status_code == 200
        models = resp.json()

        # Every model should have the new fields
        for m in models:
            assert "model_type" in m
            assert "tokens_per_second" in m

        # claude-opus-4-6 should be a hybrid model
        opus = next(m for m in models if m["slug"] == "claude-opus-4-6")
        assert opus["model_type"] == "hybrid"


@pytest.mark.asyncio
async def test_xai_provider_and_grok_model():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # xAI provider exists
        providers_resp = await client.get("/api/providers")
        xai = next(p for p in providers_resp.json() if p["slug"] == "xai")
        assert xai["display_name"] == "xAI"
        assert xai["base_url"] == "https://api.x.ai/v1"

        # Grok 3 model exists under xAI
        models_resp = await client.get(f"/api/models?provider_id={xai['id']}")
        models = models_resp.json()
        assert len(models) == 1
        grok = models[0]
        assert grok["slug"] == "grok-3"
        assert grok["display_name"] == "Grok 3"
        assert grok["model_type"] == "chat"
