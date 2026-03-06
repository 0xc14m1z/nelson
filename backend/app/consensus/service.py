import asyncio
import contextlib
import time
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.consensus.broadcast import (
    Broadcast,
    StreamEvent,
    register_broadcast,
    unregister_broadcast,
)
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
        self.broadcast = Broadcast()

    def _model_id_str(self, model: LLMModel) -> str:
        return str(model.id)

    def _model_name(self, model: LLMModel) -> str:
        return (
            f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
        )

    async def run(self) -> None:
        register_broadcast(self.session_id, self.broadcast)
        try:
            await self._run_inner()
        finally:
            unregister_broadcast(self.session_id)
            self.broadcast.close()

    async def _run_inner(self) -> None:
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

                # Push phase_change after responder round
                self.broadcast.push(StreamEvent(
                    event="phase_change",
                    data={
                        "phase": "responder_done",
                        "round_number": 1,
                        "models": [
                            {
                                "llm_model_id": r["llm_model_id"],
                                "model_name": r["model_name"],
                                "confidence": r.get("confidence"),
                                "key_points": r.get("key_points"),
                            }
                            for r in round1_responses
                        ],
                    },
                ))

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
                        {
                            "llm_model_id": cr["llm_model_id"],
                            "model_name": cr["model_name"],
                            "response": cr["response"],
                        }
                        for cr in critique_results
                    ]

                    # Push phase_change after critic round
                    self.broadcast.push(StreamEvent(
                        event="phase_change",
                        data={
                            "phase": "critic_done",
                            "round_number": round_num,
                            "models": [
                                {
                                    "llm_model_id": cr["llm_model_id"],
                                    "model_name": cr["model_name"],
                                    "disagreements": cr.get("disagreements"),
                                }
                                for cr in critique_results
                            ],
                        },
                    ))

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

                # Push terminal event
                self.broadcast.push(StreamEvent(
                    event=session.status,
                    data={"status": session.status},
                ))

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
    ) -> list[dict]:
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
                self.broadcast.push(StreamEvent(
                    event="model_error",
                    data={
                        "llm_model_id": self._model_id_str(model),
                        "model_name": self._model_name(model),
                        "round_number": 1,
                        "error": str(result),
                    },
                ))
            else:
                responses.append(result)
        await db.commit()
        return responses

    async def _call_responder(
        self, db: AsyncSession, session: Session, model: LLMModel, prompt: str
    ) -> dict:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            model_id_str = self._model_id_str(model)
            model_name = self._model_name(model)
            start = time.monotonic()

            self.broadcast.push(StreamEvent(
                event="model_start",
                data={
                    "llm_model_id": model_id_str,
                    "model_name": model_name,
                    "round_number": 1,
                    "role": "responder",
                },
            ))

            with _resolve_override(responder_agent, resolved):
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                        async with responder_agent.run_stream(prompt) as result:
                            prev_text = ""
                            async for response, last in result.stream_responses(
                                debounce_by=0.01,
                            ):
                                try:
                                    partial = await result.validate_response_output(
                                        response, allow_partial=not last,
                                    )
                                    current_text = partial.response
                                    if len(current_text) > len(prev_text):
                                        delta = current_text[len(prev_text):]
                                        self.broadcast.accumulate_text(
                                            model_id_str, delta,
                                        )
                                        self.broadcast.push(StreamEvent(
                                            event="token_delta",
                                            data={
                                                "llm_model_id": model_id_str,
                                                "round_number": 1,
                                                "delta": delta,
                                            },
                                        ))
                                        prev_text = current_text
                                except ValidationError:
                                    continue
                            output = await result.get_output()
                            usage = result.usage()
                except TimeoutError:
                    raise TimeoutError(
                        f"Timed out after {LLM_TIMEOUT_SECONDS}s"
                    )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=1,
                role="responder",
                prompt=prompt,
                response=output.response,
                confidence=output.confidence,
                key_points=output.key_points,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            self.broadcast.clear_text(model_id_str)
            self.broadcast.push(StreamEvent(
                event="model_done",
                data={
                    "llm_model_id": model_id_str,
                    "model_name": model_name,
                    "round_number": 1,
                    "role": "responder",
                    "response": output.response,
                    "structured": {
                        "confidence": output.confidence,
                        "key_points": output.key_points,
                    },
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "cost": 0,
                    "duration_ms": elapsed_ms,
                },
            ))

            return {
                "llm_model_id": model_id_str,
                "model_name": model_name,
                "response": output.response,
                "confidence": output.confidence,
                "key_points": output.key_points,
            }

    async def _run_critic_round(
        self,
        db: AsyncSession,
        session: Session,
        latest_responses: list[dict],
        prior_summary: str | None,
        round_number: int,
    ) -> list[dict]:
        # build_critic_prompt expects dicts with 'model_name' and 'response' keys
        prompt_responses = [
            {"model_name": r["model_name"], "response": r["response"]}
            for r in latest_responses
        ]
        tasks = [
            self._call_critic(
                db, session, model, prompt_responses, prior_summary, round_number
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
                self.broadcast.push(StreamEvent(
                    event="model_error",
                    data={
                        "llm_model_id": self._model_id_str(model),
                        "model_name": self._model_name(model),
                        "round_number": round_number,
                        "error": str(result),
                    },
                ))
            else:
                critique_results.append(result)
        await db.commit()
        return critique_results

    async def _call_critic(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        prompt_responses: list[dict[str, str]],
        prior_summary: str | None,
        round_number: int,
    ) -> dict:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            model_id_str = self._model_id_str(model)
            model_name = self._model_name(model)
            prompt = build_critic_prompt(
                session.enquiry, prior_summary, prompt_responses,
            )
            start = time.monotonic()

            self.broadcast.push(StreamEvent(
                event="model_start",
                data={
                    "llm_model_id": model_id_str,
                    "model_name": model_name,
                    "round_number": round_number,
                    "role": "critic",
                },
            ))

            with _resolve_override(critic_agent, resolved):
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                        async with critic_agent.run_stream(prompt) as result:
                            prev_text = ""
                            async for response, last in result.stream_responses(
                                debounce_by=0.01,
                            ):
                                try:
                                    partial = await result.validate_response_output(
                                        response, allow_partial=not last,
                                    )
                                    current_text = partial.revised_response
                                    if len(current_text) > len(prev_text):
                                        delta = current_text[len(prev_text):]
                                        self.broadcast.accumulate_text(
                                            model_id_str, delta,
                                        )
                                        self.broadcast.push(StreamEvent(
                                            event="token_delta",
                                            data={
                                                "llm_model_id": model_id_str,
                                                "round_number": round_number,
                                                "delta": delta,
                                            },
                                        ))
                                        prev_text = current_text
                                except ValidationError:
                                    continue
                            output = await result.get_output()
                            usage = result.usage()
                except TimeoutError:
                    raise TimeoutError(
                        f"Timed out after {LLM_TIMEOUT_SECONDS}s"
                    )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=round_number,
                role="critic",
                prompt=prompt,
                response=output.revised_response,
                has_disagreements=output.has_disagreements,
                disagreements=output.disagreements,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            self.broadcast.clear_text(model_id_str)
            self.broadcast.push(StreamEvent(
                event="model_done",
                data={
                    "llm_model_id": model_id_str,
                    "model_name": model_name,
                    "round_number": round_number,
                    "role": "critic",
                    "response": output.revised_response,
                    "structured": {
                        "has_disagreements": output.has_disagreements,
                        "disagreements": output.disagreements,
                    },
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "cost": 0,
                    "duration_ms": elapsed_ms,
                },
            ))

            return {
                "llm_model_id": model_id_str,
                "model_name": model_name,
                "response": output.revised_response,
                "has_disagreements": output.has_disagreements,
                "disagreements": output.disagreements,
            }

    async def _run_summarizer(
        self,
        db: AsyncSession,
        session: Session,
        responses: list[dict],
        round_number: int,
    ) -> str:
        # build_summarizer_prompt expects dicts with 'model_name' and 'response'
        prompt_responses = [
            {"model_name": r["model_name"], "response": r["response"]}
            for r in responses
        ]

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
                f"{r['model_name']}: {r['response'][:200]}"
                for r in prompt_responses
            )

        prompt = build_summarizer_prompt(prompt_responses)
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

            # Push round_summary event
            self.broadcast.push(StreamEvent(
                event="round_summary",
                data={
                    "round_number": round_number,
                    "summary": result.output.summary,
                    "agreements": result.output.agreements,
                    "disagreements": result.output.disagreements,
                    "shifts": result.output.shifts,
                },
            ))

            return result.output.summary

        except Exception:
            return "\n".join(
                f"{r['model_name']}: {r['response'][:200]}"
                for r in prompt_responses
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
        self.broadcast.push(StreamEvent(
            event="failed",
            data={"status": "failed"},
        ))

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
