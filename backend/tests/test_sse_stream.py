import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from app.agent.consensus_agent import (
    critic_agent,
    disagreement_agent,
    final_summarizer_agent,
    responder_agent,
    scorer_agent,
)
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
async def test_sse_replay_completed_session():
    """Create a session, wait for completion, then verify SSE replay."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sse-replay@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            scorer_agent.override(model=TestModel()),
            disagreement_agent.override(model=TestModel()),
            final_summarizer_agent.override(model=TestModel()),
        ):
            create_resp = await client.post(
                "/api/sessions",
                json={
                    "enquiry": "SSE test question",
                    "model_ids": model_ids,
                },
                headers=headers,
            )
            assert create_resp.status_code == 201
            session_id = create_resp.json()["id"]

            # Wait for orchestrator to finish
            await asyncio.sleep(3)

        # Now stream the completed session
        async with client.stream(
            "GET",
            f"/api/sessions/{session_id}/stream",
            headers=headers,
        ) as response:
            assert response.status_code == 200
            events = []
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "consensus_reached" in line or "max_rounds_reached" in line:
                    break

        assert len(events) > 0
        assert events[-1] in ("consensus_reached", "max_rounds_reached", "failed")


@pytest.mark.asyncio
async def test_sse_stream_not_found():
    """SSE stream returns 404 for non-existent session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _get_auth_token(client, "sse-notfound@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get(
            f"/api/sessions/{uuid.uuid4()}/stream",
            headers=headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_stream_other_user_session():
    """SSE stream returns 404 for another user's session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create session as user 1
        token1 = await _get_auth_token(client, "sse-user1@example.com")
        headers1 = {"Authorization": f"Bearer {token1}"}
        model_ids = await _get_model_ids(client)

        with (
            responder_agent.override(model=TestModel()),
            critic_agent.override(model=TestModel()),
            scorer_agent.override(model=TestModel()),
            disagreement_agent.override(model=TestModel()),
            final_summarizer_agent.override(model=TestModel()),
        ):
            create_resp = await client.post(
                "/api/sessions",
                json={"enquiry": "Private question", "model_ids": model_ids},
                headers=headers1,
            )
            session_id = create_resp.json()["id"]

        # Try to access as user 2
        token2 = await _get_auth_token(client, "sse-user2@example.com")
        headers2 = {"Authorization": f"Bearer {token2}"}

        resp = await client.get(
            f"/api/sessions/{session_id}/stream",
            headers=headers2,
        )
        assert resp.status_code == 404
