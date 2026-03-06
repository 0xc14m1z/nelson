import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.dependencies import get_current_user
from app.consensus.schemas import (
    CreateSessionRequest,
    LLMCallResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.consensus.service import ConsensusOrchestrator
from app.database import get_db
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
