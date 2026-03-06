import asyncio
import contextlib
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import (
    critic_agent,
    disagreement_agent,
    final_summarizer_agent,
    responder_agent,
    scorer_agent,
)
from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.agent.prompts import (
    build_critic_prompt,
    build_disagreement_prompt,
    build_final_summary_prompt,
    build_responder_prompt,
    build_scorer_prompt,
)
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

    def _find_model(self, model_id_str: str) -> LLMModel | None:
        for m in self._active_models:
            if str(m.id) == model_id_str:
                return m
        return None

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

            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            start_time = time.monotonic()

            try:
                await self.broadcast.wait_for_subscriber(timeout=5.0)

                # ── Round 1: Initial responses ────────────────────────
                session.status = "responding"
                session.current_round = 1
                await db.commit()

                round1_responses = await self._run_responder_round(db, session)
                if len(self._active_models) < 2:
                    await self._fail_session(db, session, start_time)
                    return

                # Score each response (non-streamed, concurrent)
                await self._run_scoring_round(db, session, round1_responses)

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

                # ── Rounds 2+: Critique loop ──────────────────────────
                latest_responses = round1_responses
                all_disagreements: list[str] = []

                for round_num in range(2, max_rounds + 1):
                    session.status = "critiquing"
                    session.current_round = round_num
                    await db.commit()

                    critique_results = await self._run_critic_round(
                        db, session, latest_responses, all_disagreements, round_num
                    )
                    if len(self._active_models) < 2:
                        await self._fail_session(db, session, start_time)
                        return

                    # Disagreement check (non-streamed, concurrent)
                    await self._run_disagreement_round(
                        db, session, critique_results, round_num
                    )

                    all_agree = all(
                        not cr["has_disagreements"] for cr in critique_results
                    )

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
                        latest_responses = critique_results
                        break

                    # Accumulate disagreements for next round
                    all_disagreements = []
                    for cr in critique_results:
                        all_disagreements.extend(cr.get("disagreements") or [])

                    latest_responses = critique_results
                else:
                    session.status = "max_rounds_reached"

                # ── Final summarizer (only on consensus) ──────────────
                if session.status == "consensus_reached":
                    session.status = "summarizing"
                    await db.commit()
                    await self._run_final_summarizer(db, session, latest_responses)
                    session.status = "consensus_reached"

                elapsed = int((time.monotonic() - start_time) * 1000)
                session.total_duration_ms = elapsed
                session.completed_at = datetime.now(UTC)
                await self._update_session_totals(db, session)
                await db.commit()

                self.broadcast.push(StreamEvent(
                    event=session.status,
                    data={
                        "status": session.status,
                        "current_round": session.current_round,
                        "total_input_tokens": session.total_input_tokens,
                        "total_output_tokens": session.total_output_tokens,
                        "total_cost": float(session.total_cost),
                        "total_duration_ms": session.total_duration_ms,
                    },
                ))

            except Exception:
                await self._fail_session(db, session, start_time)
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()

    # ── Helpers ───────────────────────────────────────────────────────

    async def _try_resolve(self, model: LLMModel, db: AsyncSession):
        try:
            return await resolve_model(self.user_id, model, db)
        except NoKeyAvailableError:
            return None

    # ── Streamed text call (shared by responder + critic + summarizer) ─

    async def _stream_text_call(
        self,
        agent,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        prompt: str,
        round_number: int,
        role: str,
    ) -> dict:
        """Run a streamed str agent. Returns dict with response text + usage."""
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
                    "round_number": round_number,
                    "role": role,
                },
            ))

            with _resolve_override(agent, resolved):
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                        async with agent.run_stream(prompt) as result:
                            prev_text = ""
                            async for chunk in result.stream_text(
                                delta=False, debounce_by=0.01,
                            ):
                                if len(chunk) > len(prev_text):
                                    delta = chunk[len(prev_text):]
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
                                    prev_text = chunk
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
                role=role,
                prompt=prompt,
                response=output,
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
                    "role": role,
                    "response": output,
                    "structured": {},
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "cost": 0,
                    "duration_ms": elapsed_ms,
                },
            ))

            return {
                "llm_model_id": model_id_str,
                "model_name": model_name,
                "response": output,
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
            }

    # ── Round runners ─────────────────────────────────────────────────

    async def _run_responder_round(
        self, db: AsyncSession, session: Session
    ) -> list[dict]:
        prompt = build_responder_prompt(session.enquiry)
        tasks = [
            self._stream_text_call(
                responder_agent, db, session, model, prompt, 1, "responder"
            )
            for model in list(self._active_models)
        ]
        return await self._gather_with_errors(
            db, session, tasks, list(self._active_models), 1, "responder"
        )

    async def _run_scoring_round(
        self, db: AsyncSession, session: Session, responses: list[dict]
    ) -> None:
        """Non-streamed: extract confidence + key_points for each response."""
        tasks = []
        for r in responses:
            model = self._find_model(r["llm_model_id"])
            if not model:
                continue
            tasks.append(
                self._score_response(db, session, model, r)
            )
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.commit()

    async def _score_response(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        response_data: dict,
    ) -> None:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            prompt = build_scorer_prompt(session.enquiry, response_data["response"])
            with _resolve_override(scorer_agent, resolved):
                result = await asyncio.wait_for(
                    scorer_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
            response_data["confidence"] = result.output.confidence
            response_data["key_points"] = result.output.key_points

            await db.execute(
                update(LLMCall)
                .where(
                    LLMCall.session_id == session.id,
                    LLMCall.llm_model_id == model.id,
                    LLMCall.round_number == 1,
                    LLMCall.role == "responder",
                )
                .values(
                    confidence=result.output.confidence,
                    key_points=result.output.key_points,
                )
            )

    async def _run_critic_round(
        self,
        db: AsyncSession,
        session: Session,
        latest_responses: list[dict],
        disagreements: list[str],
        round_number: int,
    ) -> list[dict]:
        prompt_responses = [
            {"model_name": r["model_name"], "response": r["response"]}
            for r in latest_responses
        ]
        tasks = []
        for model in list(self._active_models):
            prompt = build_critic_prompt(
                session.enquiry, prompt_responses,
                disagreements if disagreements else None,
            )
            tasks.append(
                self._stream_text_call(
                    critic_agent, db, session, model, prompt,
                    round_number, "critic",
                )
            )
        return await self._gather_with_errors(
            db, session, tasks, list(self._active_models),
            round_number, "critic"
        )

    async def _run_disagreement_round(
        self,
        db: AsyncSession,
        session: Session,
        critique_results: list[dict],
        round_number: int,
    ) -> None:
        """Non-streamed: check disagreements for each critic response."""
        prompt_responses = [
            {"model_name": r["model_name"], "response": r["response"]}
            for r in critique_results
        ]
        tasks = []
        for r in critique_results:
            model = self._find_model(r["llm_model_id"])
            if not model:
                continue
            tasks.append(
                self._check_disagreements(
                    db, session, model, r, prompt_responses, round_number
                )
            )
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.commit()

    async def _check_disagreements(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        response_data: dict,
        all_responses: list[dict[str, str]],
        round_number: int,
    ) -> None:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            prompt = build_disagreement_prompt(session.enquiry, all_responses)
            with _resolve_override(disagreement_agent, resolved):
                result = await asyncio.wait_for(
                    disagreement_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
            response_data["has_disagreements"] = result.output.has_disagreements
            response_data["disagreements"] = result.output.disagreements

            await db.execute(
                update(LLMCall)
                .where(
                    LLMCall.session_id == session.id,
                    LLMCall.llm_model_id == model.id,
                    LLMCall.round_number == round_number,
                    LLMCall.role == "critic",
                )
                .values(
                    has_disagreements=result.output.has_disagreements,
                    disagreements=result.output.disagreements,
                )
            )

    async def _run_final_summarizer(
        self,
        db: AsyncSession,
        session: Session,
        final_responses: list[dict],
    ) -> None:
        """Streamed: produce the consensus answer."""
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
            result = await db.execute(
                select(LLMModel).where(LLMModel.slug == "gpt-4o-mini")
            )
            summarizer_llm = result.scalar_one_or_none()

        if not summarizer_llm:
            return

        prompt_responses = [
            {"model_name": r["model_name"], "response": r["response"]}
            for r in final_responses
        ]
        prompt = build_final_summary_prompt(session.enquiry, prompt_responses)

        resolved = await self._try_resolve(summarizer_llm, db)
        model_id_str = self._model_id_str(summarizer_llm)
        model_name = self._model_name(summarizer_llm)
        start = time.monotonic()

        self.broadcast.push(StreamEvent(
            event="model_start",
            data={
                "llm_model_id": model_id_str,
                "model_name": model_name,
                "round_number": session.current_round,
                "role": "summarizer",
            },
        ))

        with _resolve_override(final_summarizer_agent, resolved):
            try:
                async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                    async with final_summarizer_agent.run_stream(prompt) as result:
                        prev_text = ""
                        async for chunk in result.stream_text(
                            delta=False, debounce_by=0.01,
                        ):
                            if len(chunk) > len(prev_text):
                                delta = chunk[len(prev_text):]
                                self.broadcast.accumulate_text(model_id_str, delta)
                                self.broadcast.push(StreamEvent(
                                    event="token_delta",
                                    data={
                                        "llm_model_id": model_id_str,
                                        "round_number": session.current_round,
                                        "delta": delta,
                                    },
                                ))
                                prev_text = chunk
                        output = await result.get_output()
                        usage = result.usage()
            except TimeoutError:
                return

        elapsed_ms = int((time.monotonic() - start) * 1000)

        call = LLMCall(
            session_id=session.id,
            llm_model_id=summarizer_llm.id,
            round_number=session.current_round,
            role="summarizer",
            prompt=prompt,
            response=output,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cost=0,
            duration_ms=elapsed_ms,
        )
        db.add(call)
        await db.commit()

        self.broadcast.clear_text(model_id_str)
        self.broadcast.push(StreamEvent(
            event="model_done",
            data={
                "llm_model_id": model_id_str,
                "model_name": model_name,
                "round_number": session.current_round,
                "role": "summarizer",
                "response": output,
                "structured": {},
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
                "cost": 0,
                "duration_ms": elapsed_ms,
            },
        ))

    # ── Shared helpers ────────────────────────────────────────────────

    async def _gather_with_errors(
        self,
        db: AsyncSession,
        session: Session,
        tasks: list,
        models: list[LLMModel],
        round_number: int,
        role: str,
    ) -> list[dict]:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        responses = []
        for model, result in zip(models, results):
            if isinstance(result, Exception):
                await self._record_error(
                    db, session, model, round_number, role, str(result)
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
                responses.append(result)
        await db.commit()
        return responses

    async def _record_error(
        self, db: AsyncSession, session: Session,
        model: LLMModel, round_number: int, role: str, error: str,
    ) -> None:
        call = LLMCall(
            session_id=session.id, llm_model_id=model.id,
            round_number=round_number, role=role, error=error,
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
            data={
                "status": "failed",
                "current_round": session.current_round,
                "total_input_tokens": session.total_input_tokens,
                "total_output_tokens": session.total_output_tokens,
                "total_cost": float(session.total_cost),
                "total_duration_ms": session.total_duration_ms,
            },
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
    from datetime import timedelta
    async with async_session_factory() as db:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        result = await db.execute(
            select(Session).where(
                Session.status.in_(["pending", "responding", "critiquing", "summarizing"]),
                Session.last_heartbeat_at < cutoff,
            )
        )
        for session in result.scalars().all():
            session.status = "failed"
            session.completed_at = datetime.now(UTC)
        await db.commit()
