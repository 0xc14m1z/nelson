import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.main import app
from tests.conftest import extract_token_from_mailpit


async def _get_auth_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/auth/magic-link", json={"email": email})
    token = await extract_token_from_mailpit(email)
    resp = await client.post("/api/auth/verify", json={"email": email, "token": token})
    return resp.json()["access_token"]


async def _get_model_ids(client: AsyncClient) -> list[str]:
    resp = await client.get("/api/models")
    models = resp.json()
    return [m["id"] for m in models[:2]]


@pytest.mark.asyncio
async def test_create_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-create@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            summarizer_agent.override(model=TestModel()),
        ):
            resp = await client.post(
                "/api/sessions",
                json={
                    "enquiry": "What is the speed of light?",
                    "model_ids": model_ids,
                },
                headers=headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["enquiry"] == "What is the speed of light?"
        assert len(data["model_ids"]) == 2


@pytest.mark.asyncio
async def test_create_session_requires_min_2_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-min2@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        resp = await client.post(
            "/api/sessions",
            json={"enquiry": "Test", "model_ids": [model_ids[0]]},
            headers=headers,
        )
        assert resp.status_code == 422  # Pydantic validation: min_length=2


@pytest.mark.asyncio
async def test_create_session_invalid_model_ids():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/sessions",
            json={
                "enquiry": "Test",
                "model_ids": [
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_sessions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-list@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/sessions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "total" in data
        assert data["page"] == 1
        assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_get_session_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-notfound@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get(
            f"/api/sessions/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_detail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-detail@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            summarizer_agent.override(model=TestModel()),
        ):
            create_resp = await client.post(
                "/api/sessions",
                json={
                    "enquiry": "Tell me about gravity",
                    "model_ids": model_ids,
                },
                headers=headers,
            )
        session_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/sessions/{session_id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session_id
        assert data["enquiry"] == "Tell me about gravity"
        assert "llm_calls" in data


@pytest.mark.asyncio
async def test_delete_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-delete@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            summarizer_agent.override(model=TestModel()),
        ):
            create_resp = await client.post(
                "/api/sessions",
                json={
                    "enquiry": "Delete me",
                    "model_ids": model_ids,
                },
                headers=headers,
            )
        session_id = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/sessions/{session_id}", headers=headers
        )
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(
            f"/api/sessions/{session_id}", headers=headers
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-delnf@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.delete(
            f"/api/sessions/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_session_detail_includes_structured_fields():
    """Verify that GET /api/sessions/{id} returns structured fields in llm_calls."""
    import asyncio

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-structured@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            summarizer_agent.override(model=TestModel()),
        ):
            create_resp = await client.post(
                "/api/sessions",
                json={
                    "enquiry": "Structured fields test question",
                    "model_ids": model_ids,
                },
                headers=headers,
            )
            assert create_resp.status_code == 201
            session_id = create_resp.json()["id"]

            # Wait for background orchestrator to finish
            await asyncio.sleep(3)

        resp = await client.get(
            f"/api/sessions/{session_id}", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["llm_calls"]) > 0

        # Check that structured fields are present in the response schema
        for call in data["llm_calls"]:
            # All calls should have these keys (even if null)
            assert "confidence" in call
            assert "key_points" in call
            assert "has_disagreements" in call
            assert "disagreements" in call

        # Critic calls should have structured data populated by TestModel
        critic_calls = [c for c in data["llm_calls"] if c["role"] == "critic"]
        assert len(critic_calls) > 0
        for call in critic_calls:
            assert call["has_disagreements"] is not None


@pytest.mark.asyncio
async def test_list_sessions_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sess-page@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get(
            "/api/sessions?page=1&page_size=5", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
