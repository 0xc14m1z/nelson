import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sse_starlette import EventSourceResponse
from starlette.requests import Request

from app.auth.dependencies import get_current_user
from app.consensus.schemas import (
    CreateSessionRequest,
    LLMCallResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.consensus.service import ConsensusOrchestrator
from app.database import async_session_factory, get_db
from app.models import LLMCall, LLMModel, Session, User
from app.models.session import session_models

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Store background tasks to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()


def _session_to_response(session: Session, model_ids: list[UUID]) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        enquiry=session.enquiry,
        status=session.status,
        max_rounds=session.max_rounds,
        current_round=session.current_round,
        total_input_tokens=session.total_input_tokens,
        total_output_tokens=session.total_output_tokens,
        total_cost=float(session.total_cost),
        total_duration_ms=session.total_duration_ms,
        created_at=session.created_at,
        completed_at=session.completed_at,
        model_ids=model_ids,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate models exist and are active
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.id.in_(body.model_ids),
            LLMModel.is_active.is_(True),
        )
    )
    models = result.scalars().all()
    if len(models) < 2:
        raise HTTPException(400, "At least 2 valid, active models are required")
    if len(models) != len(body.model_ids):
        raise HTTPException(400, "One or more model IDs are invalid or inactive")

    session = Session(
        user_id=user.id,
        enquiry=body.enquiry,
        max_rounds=body.max_rounds,
    )
    session.models = list(models)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Launch orchestrator as background task
    orchestrator = ConsensusOrchestrator(session.id, user.id)
    task = asyncio.create_task(orchestrator.run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return _session_to_response(session, body.model_ids)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(
        select(func.count(Session.id)).where(Session.user_id == user.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    session_responses = []
    for s in sessions:
        model_result = await db.execute(
            select(session_models.c.llm_model_id).where(
                session_models.c.session_id == s.id
            )
        )
        model_ids = [row[0] for row in model_result.all()]
        session_responses.append(_session_to_response(s, model_ids))

    return SessionListResponse(
        sessions=session_responses, total=total, page=page, page_size=page_size
    )


async def _session_event_generator(request: Request, session_id: UUID, user_id: UUID):
    """Replay existing events then poll for new ones."""
    last_seen_count = 0
    keepalive_interval = 15  # seconds
    poll_interval = 1  # seconds
    polls_per_keepalive = keepalive_interval // poll_interval

    async with async_session_factory() as db:
        # Verify session belongs to user
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return

        poll_count = 0
        while True:
            if await request.is_disconnected():
                break

            # Fetch all calls after last_seen_count
            result = await db.execute(
                select(LLMCall)
                .where(LLMCall.session_id == session_id)
                .options(joinedload(LLMCall.llm_model).joinedload(LLMModel.provider))
                .order_by(LLMCall.round_number, LLMCall.created_at)
            )
            calls = result.scalars().unique().all()

            # Send new calls
            for call in calls[last_seen_count:]:
                model_slug = call.llm_model.slug
                provider_slug = call.llm_model.provider.slug
                event_type = call.role  # "responder", "critic", "summarizer"
                if call.error:
                    event_type = "model_dropped"

                yield {
                    "event": event_type,
                    "data": json.dumps({
                        "id": str(call.id),
                        "model_slug": model_slug,
                        "provider_slug": provider_slug,
                        "model_name": f"{provider_slug}/{model_slug}",
                        "round_number": call.round_number,
                        "role": call.role,
                        "response": call.response,
                        "error": call.error,
                        "input_tokens": call.input_tokens,
                        "output_tokens": call.output_tokens,
                        "cost": float(call.cost),
                        "duration_ms": call.duration_ms,
                    }),
                }
                last_seen_count += 1

            # Check session status
            await db.refresh(session)
            terminal_statuses = ("consensus_reached", "max_rounds_reached", "failed")
            if session.status in terminal_statuses:
                yield {
                    "event": session.status,
                    "data": json.dumps({
                        "status": session.status,
                        "current_round": session.current_round,
                        "total_input_tokens": session.total_input_tokens,
                        "total_output_tokens": session.total_output_tokens,
                        "total_cost": float(session.total_cost),
                        "total_duration_ms": session.total_duration_ms,
                    }),
                }
                break

            # Keepalive ping
            poll_count += 1
            if poll_count >= polls_per_keepalive:
                yield {"comment": "keepalive"}
                poll_count = 0

            await asyncio.sleep(poll_interval)


@router.get("/{session_id}/stream")
async def stream_session(
    request: Request,
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")

    return EventSourceResponse(
        _session_event_generator(request, session_id, user.id)
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")

    model_result = await db.execute(
        select(session_models.c.llm_model_id).where(
            session_models.c.session_id == session.id
        )
    )
    model_ids = [row[0] for row in model_result.all()]

    calls_result = await db.execute(
        select(LLMCall)
        .where(LLMCall.session_id == session.id)
        .options(joinedload(LLMCall.llm_model).joinedload(LLMModel.provider))
        .order_by(LLMCall.round_number, LLMCall.created_at)
    )
    calls = calls_result.scalars().unique().all()

    call_responses = [
        LLMCallResponse(
            id=c.id,
            llm_model_id=c.llm_model_id,
            model_slug=c.llm_model.slug,
            provider_slug=c.llm_model.provider.slug,
            round_number=c.round_number,
            role=c.role,
            prompt=c.prompt,
            response=c.response,
            input_tokens=c.input_tokens,
            output_tokens=c.output_tokens,
            cost=float(c.cost),
            duration_ms=c.duration_ms,
            error=c.error,
            created_at=c.created_at,
        )
        for c in calls
    ]

    return SessionDetailResponse(
        id=session.id,
        enquiry=session.enquiry,
        status=session.status,
        max_rounds=session.max_rounds,
        current_round=session.current_round,
        total_input_tokens=session.total_input_tokens,
        total_output_tokens=session.total_output_tokens,
        total_cost=float(session.total_cost),
        total_duration_ms=session.total_duration_ms,
        created_at=session.created_at,
        completed_at=session.completed_at,
        model_ids=model_ids,
        llm_calls=call_responses,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
