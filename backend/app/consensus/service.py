import asyncio
import contextlib
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.database import async_session_factory
from app.models import LLMCall, LLMModel, Session, UserSettings

MAX_ROUNDS_HARD_CAP = 20
LLM_TIMEOUT_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 10
CONCURRENCY_LIMIT = 10


def _resolve_override(agent, resolved):
    """Build an override context manager for the agent using a resolved model.

    If resolved is None (e.g. no API key available), return a no-op context
    manager so the agent uses whatever model is already configured (e.g. a
    TestModel set by an outer override in tests).
    """
    if resolved is None:
        return contextlib.nullcontext()

    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    pai_model = OpenAIChatModel(
        model_name=resolved.model_slug,
        provider=OpenAIProvider(
            base_url=resolved.base_url, api_key=resolved.api_key
        ),
    )
    return agent.override(model=pai_model)


class ConsensusOrchestrator:
    def __init__(self, session_id: UUID, user_id: UUID):
        self.session_id = session_id
        self.user_id = user_id
        self.semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        self._active_models: list[LLMModel] = []
        self._heartbeat_task: asyncio.Task | None = None

    async def run(self) -> None:
        async with async_session_factory() as db:
            session = await db.get(Session, self.session_id)
            if not session:
                return

            await db.refresh(session, attribute_names=["models"])
            self._active_models = list(session.models)
            max_rounds = session.max_rounds or MAX_ROUNDS_HARD_CAP

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            start_time = time.monotonic()

            try:
                # Round 1: Initial responses
                session.status = "responding"
                session.current_round = 1
                await db.commit()

                round1_responses = await self._run_responder_round(db, session)
                if len(self._active_models) < 2:
                    await self._fail_session(db, session, start_time)
                    return

                # Rounds 2+: Critique loop
                prior_summary: str | None = None
                latest_responses = round1_responses

                for round_num in range(2, max_rounds + 1):
                    session.status = "critiquing"
                    session.current_round = round_num
                    await db.commit()

                    # Summarize prior round
                    prior_summary = await self._run_summarizer(
                        db, session, latest_responses, round_num
                    )

                    # Run critic round
                    critique_results = await self._run_critic_round(
                        db, session, latest_responses, prior_summary, round_num
                    )

                    if len(self._active_models) < 2:
                        await self._fail_session(db, session, start_time)
                        return

                    # Check convergence
                    all_agree = all(
                        not cr["has_disagreements"] for cr in critique_results
                    )
                    latest_responses = [
                        {"model_name": cr["model_name"], "response": cr["response"]}
                        for cr in critique_results
                    ]

                    if all_agree:
                        session.status = "consensus_reached"
                        break
                else:
                    session.status = "max_rounds_reached"

                elapsed = int((time.monotonic() - start_time) * 1000)
                session.total_duration_ms = elapsed
                session.completed_at = datetime.now(UTC)
                await self._update_session_totals(db, session)
                await db.commit()

            except Exception:
                await self._fail_session(db, session, start_time)
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()

    async def _try_resolve(self, model: LLMModel, db: AsyncSession):
        """Try to resolve model credentials; return None if unavailable."""
        try:
            return await resolve_model(self.user_id, model, db)
        except NoKeyAvailableError:
            return None

    async def _run_responder_round(
        self, db: AsyncSession, session: Session
    ) -> list[dict[str, str]]:
        prompt = build_responder_prompt(session.enquiry)
        tasks = [
            self._call_responder(db, session, model, prompt)
            for model in list(self._active_models)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for model, result in zip(list(self._active_models), results):
            if isinstance(result, Exception):
                await self._record_error(db, session, model, 1, "responder", str(result))
                self._active_models.remove(model)
            else:
                responses.append(result)
        await db.commit()
        return responses

    async def _call_responder(
        self, db: AsyncSession, session: Session, model: LLMModel, prompt: str
    ) -> dict[str, str]:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            start = time.monotonic()

            with _resolve_override(responder_agent, resolved):
                result = await asyncio.wait_for(
                    responder_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=1,
                role="responder",
                prompt=prompt,
                response=result.output.response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            model_name = (
                f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            )
            return {"model_name": model_name, "response": result.output.response}

    async def _run_critic_round(
        self,
        db: AsyncSession,
        session: Session,
        latest_responses: list[dict[str, str]],
        prior_summary: str | None,
        round_number: int,
    ) -> list[dict]:
        tasks = [
            self._call_critic(
                db, session, model, latest_responses, prior_summary, round_number
            )
            for model in list(self._active_models)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        critique_results = []
        for model, result in zip(list(self._active_models), results):
            if isinstance(result, Exception):
                await self._record_error(
                    db, session, model, round_number, "critic", str(result)
                )
                self._active_models.remove(model)
            else:
                critique_results.append(result)
        await db.commit()
        return critique_results

    async def _call_critic(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        latest_responses: list[dict[str, str]],
        prior_summary: str | None,
        round_number: int,
    ) -> dict:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            prompt = build_critic_prompt(session.enquiry, prior_summary, latest_responses)
            start = time.monotonic()

            with _resolve_override(critic_agent, resolved):
                result = await asyncio.wait_for(
                    critic_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=round_number,
                role="critic",
                prompt=prompt,
                response=result.output.revised_response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            model_name = (
                f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            )
            return {
                "model_name": model_name,
                "response": result.output.revised_response,
                "has_disagreements": result.output.has_disagreements,
            }

    async def _run_summarizer(
        self,
        db: AsyncSession,
        session: Session,
        responses: list[dict[str, str]],
        round_number: int,
    ) -> str:
        # Get user's summarizer model
        settings = await db.execute(
            select(UserSettings).where(UserSettings.user_id == session.user_id)
        )
        user_settings = settings.scalar_one_or_none()

        summarizer_model_id = (
            user_settings.summarizer_model_id if user_settings else None
        )

        if summarizer_model_id:
            summarizer_llm = await db.get(LLMModel, summarizer_model_id)
        else:
            # Default to gpt-4o-mini
            result = await db.execute(
                select(LLMModel).where(LLMModel.slug == "gpt-4o-mini")
            )
            summarizer_llm = result.scalar_one_or_none()

        if not summarizer_llm:
            # Fallback: return concatenated responses as "summary"
            return "\n".join(
                f"{r['model_name']}: {r['response'][:200]}" for r in responses
            )

        prompt = build_summarizer_prompt(responses)
        start = time.monotonic()

        try:
            resolved = await self._try_resolve(summarizer_llm, db)

            with _resolve_override(summarizer_agent, resolved):
                result = await asyncio.wait_for(
                    summarizer_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=summarizer_llm.id,
                round_number=round_number,
                role="summarizer",
                prompt=prompt,
                response=result.output.summary,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)
            await db.commit()
            return result.output.summary

        except Exception:
            return "\n".join(
                f"{r['model_name']}: {r['response'][:200]}" for r in responses
            )

    async def _record_error(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        round_number: int,
        role: str,
        error: str,
    ) -> None:
        call = LLMCall(
            session_id=session.id,
            llm_model_id=model.id,
            round_number=round_number,
            role=role,
            error=error,
        )
        db.add(call)

    async def _fail_session(
        self, db: AsyncSession, session: Session, start_time: float
    ) -> None:
        session.status = "failed"
        session.total_duration_ms = int((time.monotonic() - start_time) * 1000)
        session.completed_at = datetime.now(UTC)
        await self._update_session_totals(db, session)
        await db.commit()

    async def _update_session_totals(
        self, db: AsyncSession, session: Session
    ) -> None:
        result = await db.execute(
            select(LLMCall).where(LLMCall.session_id == session.id)
        )
        calls = result.scalars().all()
        session.total_input_tokens = sum(c.input_tokens for c in calls)
        session.total_output_tokens = sum(c.output_tokens for c in calls)
        session.total_cost = sum(float(c.cost) for c in calls)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                async with async_session_factory() as db:
                    session = await db.get(Session, self.session_id)
                    if session:
                        session.last_heartbeat_at = datetime.now(UTC)
                        await db.commit()
            except Exception:
                pass


async def cleanup_orphaned_sessions() -> None:
    """Mark stuck sessions as failed. Call on app startup."""
    from datetime import timedelta

    async with async_session_factory() as db:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        result = await db.execute(
            select(Session).where(
                Session.status.in_(["pending", "responding", "critiquing"]),
                Session.last_heartbeat_at < cutoff,
            )
        )
        for session in result.scalars().all():
            session.status = "failed"
            session.completed_at = datetime.now(UTC)
        await db.commit()
