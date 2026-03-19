"""Consensus orchestrator — happy-path consensus loop.

Coordinates the multi-model consensus workflow:
task framing → contributions → synthesis → review → release gate.

Phase 6 implements only the happy path: all reviews approve (or minor_revise),
no framing updates, no retries or repair.
"""

import asyncio

from nelson.core.events import EventEmitter
from nelson.prompts.moderator import (
    build_framing_messages,
    build_release_gate_messages,
    build_synthesis_messages,
)
from nelson.prompts.participant import (
    build_contribution_messages,
    build_review_messages,
)
from nelson.protocols.domain import (
    CandidateSynthesisResult,
    ParticipantContribution,
    ReleaseGateResult,
    ReviewResult,
    TaskFramingResult,
    UsageSnapshot,
)
from nelson.protocols.enums import (
    Adapter,
    CandidateSource,
    ConsensusStatus,
    EventType,
    FinishReason,
    InvocationPurpose,
    OutputFormat,
    Phase,
    ReleaseGateDecision,
    ReleaseGateMode,
    ReviewDecision,
    Role,
    RunStatus,
    UsageScope,
)
from nelson.protocols.events import (
    CandidateCreatedPayload,
    CommandCompletedPayload,
    CommandReceivedPayload,
    ConsensusReachedPayload,
    ModelCompletedPayload,
    ModelStartedPayload,
    ReleaseGateCompletedPayload,
    ReleaseGateStartedPayload,
    ReviewCompletedPayload,
    ReviewStartedPayload,
    RoundCompletedPayload,
    RoundStartedPayload,
    RunCompletedPayload,
    RunStartedPayload,
    TaskFramingCompletedPayload,
    TaskFramingStartedPayload,
    UsageReportedPayload,
)
from nelson.protocols.results import (
    RunConsensusInfo,
    RunInputInfo,
    RunInvocationUsage,
    RunModelsInfo,
    RunReleaseGateInfo,
    RunResult,
    RunTaskFramingInfo,
    RunTimingInfo,
    RunUsageInfo,
)
from nelson.providers.base import Provider, ProviderResponse
from nelson.utils.clock import duration_ms, utc_now_iso
from nelson.utils.ids import make_candidate_id, make_invocation_id


async def _invoke_structured(
    provider: Provider,
    model: str,
    messages: list[dict[str, str]],
    # Schema enforcement for provider-side validation deferred to later phases
    schema: dict[str, object] | None = None,
) -> ProviderResponse:
    """Invoke the provider and return the response.

    Wrapper that can later add repair logic (Phase 8).
    """
    return await provider.invoke(model, messages, response_schema=schema)


async def run_consensus(
    *,
    prompt_text: str,
    participants: list[str],
    moderator: str,
    max_rounds: int,
    release_gate_mode: ReleaseGateMode,
    adapter: Adapter,
    provider: Provider,
    emitter: EventEmitter,
) -> RunResult:
    """Execute a happy-path consensus run.

    Coordinates all consensus phases and emits events via the emitter.
    Returns a fully populated RunResult.

    Phase 6 limitation: only handles the happy path where all reviewers
    approve or request only minor revisions. Multi-round, framing updates,
    retry, and repair are deferred to later phases.
    """
    started_at = utc_now_iso()
    invocation_usages: list[RunInvocationUsage] = []

    # ── command_received ────────────────────────────────────────────────
    emitter.emit(
        event_type=EventType.COMMAND_RECEIVED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=CommandReceivedPayload(
            command_type="run",
            adapter=adapter,
        ),
    )

    # ── run_started ─────────────────────────────────────────────────────
    emitter.emit(
        event_type=EventType.RUN_STARTED,
        phase=Phase.STARTUP,
        role=Role.SYSTEM,
        payload=RunStartedPayload(
            input_source="prompt",
            max_rounds=max_rounds,
            release_gate_mode=release_gate_mode,
            participants=participants,
            moderator=moderator,
        ),
    )

    # ── 1. Task Framing ─────────────────────────────────────────────────
    framing_inv_id = make_invocation_id()
    emitter.emit(
        event_type=EventType.TASK_FRAMING_STARTED,
        phase=Phase.TASK_FRAMING,
        role=Role.MODERATOR,
        model=moderator,
        payload=TaskFramingStartedPayload(
            invocation_id=framing_inv_id,
            schema_name=TaskFramingResult.__name__,
            # Phase 6 uses invoke() (non-streaming); streaming deferred to later phases
            streaming=False,
        ),
    )

    framing_response = await _invoke_structured(
        provider,
        moderator,
        build_framing_messages(
            user_prompt=prompt_text,
            max_rounds=max_rounds,
            release_gate_mode=release_gate_mode,
        ),
    )
    framing = TaskFramingResult.model_validate(framing_response.parsed)
    _record_usage(invocation_usages, framing_inv_id, moderator, Role.MODERATOR,
                  InvocationPurpose.TASK_FRAMING, framing_response.usage)

    emitter.emit(
        event_type=EventType.TASK_FRAMING_COMPLETED,
        phase=Phase.TASK_FRAMING,
        role=Role.MODERATOR,
        model=moderator,
        payload=TaskFramingCompletedPayload(
            invocation_id=framing_inv_id,
            task_type=framing.task_type,
            sensitivity=framing.sensitivity,
            objective=framing.objective,
            quality_criteria=framing.quality_criteria,
            aspects_to_cover=framing.aspects_to_cover,
            ambiguities=framing.ambiguities,
            assumptions=framing.assumptions,
            # Phase 6 is single-framing-version; multi-version support added in Phase 7
            framing_version=1,
        ),
    )

    # ── 2. Participant Contributions (parallel) ──────────────────────────
    # Participants are independent — invoke all concurrently via gather().
    # Events are emitted in deterministic participant order: all MODEL_STARTED
    # before the gather, all MODEL_COMPLETED after, preserving a clean stream.
    contrib_inv_ids: list[str] = []
    for participant in participants:
        inv_id = make_invocation_id()
        contrib_inv_ids.append(inv_id)
        emitter.emit(
            event_type=EventType.MODEL_STARTED,
            phase=Phase.PARTICIPANT_GENERATION,
            role=Role.PARTICIPANT,
            model=participant,
            payload=ModelStartedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.INITIAL_CONTRIBUTION,
                framing_version=1,
                schema_name=ParticipantContribution.__name__,
                # Phase 6 uses invoke() (non-streaming); streaming deferred
                streaming=False,
            ),
        )

    contrib_responses = await asyncio.gather(*(
        _invoke_structured(
            provider,
            participant,
            build_contribution_messages(
                user_prompt=prompt_text,
                framing=framing,
                participant_model=participant,
            ),
        )
        for participant in participants
    ))

    contributions: list[ParticipantContribution] = []
    for participant, inv_id, response in zip(
        participants, contrib_inv_ids, contrib_responses, strict=True,
    ):
        contribution = ParticipantContribution.model_validate(response.parsed)
        contributions.append(contribution)
        _record_usage(invocation_usages, inv_id, participant, Role.PARTICIPANT,
                      InvocationPurpose.INITIAL_CONTRIBUTION, response.usage)
        emitter.emit(
            event_type=EventType.MODEL_COMPLETED,
            phase=Phase.PARTICIPANT_GENERATION,
            role=Role.PARTICIPANT,
            model=participant,
            payload=ModelCompletedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.INITIAL_CONTRIBUTION,
                framing_version=1,
                finish_reason=FinishReason.STOP,
                output_format=OutputFormat.STRUCTURED,
            ),
        )

    # ── 3. Candidate Synthesis ──────────────────────────────────────────
    synthesis_inv_id = make_invocation_id()
    emitter.emit(
        event_type=EventType.MODEL_STARTED,
        phase=Phase.CANDIDATE_SYNTHESIS,
        role=Role.MODERATOR,
        model=moderator,
        payload=ModelStartedPayload(
            invocation_id=synthesis_inv_id,
            purpose=InvocationPurpose.CANDIDATE_SYNTHESIS,
            framing_version=1,
            schema_name=CandidateSynthesisResult.__name__,
            streaming=False,
        ),
    )

    synthesis_response = await _invoke_structured(
        provider,
        moderator,
        build_synthesis_messages(
            user_prompt=prompt_text,
            framing=framing,
            contributions=contributions,
            round_number=1,
        ),
    )
    synthesis = CandidateSynthesisResult.model_validate(synthesis_response.parsed)
    _record_usage(invocation_usages, synthesis_inv_id, moderator, Role.MODERATOR,
                  InvocationPurpose.CANDIDATE_SYNTHESIS, synthesis_response.usage)

    emitter.emit(
        event_type=EventType.MODEL_COMPLETED,
        phase=Phase.CANDIDATE_SYNTHESIS,
        role=Role.MODERATOR,
        model=moderator,
        payload=ModelCompletedPayload(
            invocation_id=synthesis_inv_id,
            purpose=InvocationPurpose.CANDIDATE_SYNTHESIS,
            framing_version=1,
            finish_reason=FinishReason.STOP,
            output_format=OutputFormat.STRUCTURED,
        ),
    )

    candidate_id = make_candidate_id()
    emitter.emit(
        event_type=EventType.CANDIDATE_CREATED,
        phase=Phase.CANDIDATE_SYNTHESIS,
        role=Role.MODERATOR,
        model=moderator,
        payload=CandidateCreatedPayload(
            candidate_id=candidate_id,
            framing_version=1,
            source=CandidateSource.INITIAL_SYNTHESIS,
            text=synthesis.candidate_markdown,
            summary=synthesis.summary,
            excerpt_count=len(synthesis.relevant_excerpt_labels),
        ),
    )

    # ── 4. Participant Reviews ──────────────────────────────────────────
    # Round 1 starts
    emitter.emit(
        event_type=EventType.ROUND_STARTED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=1,
        payload=RoundStartedPayload(
            round=1,
            candidate_id=candidate_id,
            framing_version=1,
            target_participant_count=len(participants),
        ),
    )

    emitter.emit(
        event_type=EventType.REVIEW_STARTED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=1,
        payload=ReviewStartedPayload(
            candidate_id=candidate_id,
            framing_version=1,
            target_participant_count=len(participants),
        ),
    )

    # Emit all review MODEL_STARTED events, then gather calls in parallel
    review_inv_ids: list[str] = []
    for participant in participants:
        inv_id = make_invocation_id()
        review_inv_ids.append(inv_id)
        emitter.emit(
            event_type=EventType.MODEL_STARTED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.PARTICIPANT,
            model=participant,
            round_number=1,
            payload=ModelStartedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.CANDIDATE_REVIEW,
                framing_version=1,
                schema_name=ReviewResult.__name__,
                streaming=False,
            ),
        )

    review_responses = await asyncio.gather(*(
        _invoke_structured(
            provider,
            participant,
            build_review_messages(
                user_prompt=prompt_text,
                framing=framing,
                candidate_markdown=synthesis.candidate_markdown,
                synthesis_summary=synthesis.summary,
                contributions=contributions,
                participant_model=participant,
            ),
        )
        for participant in participants
    ))

    reviews: list[ReviewResult] = []
    approve_count = 0
    minor_count = 0

    for participant, inv_id, response in zip(
        participants, review_inv_ids, review_responses, strict=True,
    ):
        review = ReviewResult.model_validate(response.parsed)
        reviews.append(review)
        _record_usage(invocation_usages, inv_id, participant, Role.PARTICIPANT,
                      InvocationPurpose.CANDIDATE_REVIEW, response.usage)

        if review.decision == ReviewDecision.APPROVE:
            approve_count += 1
        elif review.decision == ReviewDecision.MINOR_REVISE:
            minor_count += 1

        emitter.emit(
            event_type=EventType.MODEL_COMPLETED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.PARTICIPANT,
            model=participant,
            round_number=1,
            payload=ModelCompletedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.CANDIDATE_REVIEW,
                framing_version=1,
                finish_reason=FinishReason.STOP,
                output_format=OutputFormat.STRUCTURED,
            ),
        )

    emitter.emit(
        event_type=EventType.REVIEW_COMPLETED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=1,
        payload=ReviewCompletedPayload(
            candidate_id=candidate_id,
            framing_version=1,
            reviewer_count=len(participants),
            approve_count=approve_count,
            minor_revise_count=minor_count,
            # Happy-path assumption: Phase 6 only handles approve/minor_revise
            major_revise_count=0,
            reject_count=0,
        ),
    )

    # ── 5. Consensus Reached ────────────────────────────────────────────
    # In the happy path, all reviews approve or minor_revise

    # Build consensus summary from actual vote distribution
    if minor_count > 0:
        consensus_summary = f"{approve_count} approved, {minor_count} requested minor revisions"
    else:
        consensus_summary = "All participants approved the candidate"

    emitter.emit(
        event_type=EventType.CONSENSUS_REACHED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=1,
        payload=ConsensusReachedPayload(
            candidate_id=candidate_id,
            reviewer_count=len(participants),
            approve_count=approve_count,
            minor_revise_count=minor_count,
            major_revise_count=0,
            reject_count=0,
            summary=consensus_summary,
        ),
    )

    # Round 1 completed
    emitter.emit(
        event_type=EventType.ROUND_COMPLETED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=1,
        payload=RoundCompletedPayload(
            round=1,
            candidate_id=candidate_id,
            framing_version=1,
            review_executed=True,
            approve_count=approve_count,
            minor_revise_count=minor_count,
            major_revise_count=0,
            reject_count=0,
            # Phase 6 is single-round only; multi-round logic added in Phase 7
            will_continue=False,
        ),
    )

    # ── 6. Release Gate ─────────────────────────────────────────────────
    final_answer: str
    gate_executed: bool
    gate_decision: ReleaseGateDecision
    gate_summary: str
    gate_minor_fixes: list[str] = []
    gate_blocking: list[str] = []

    if release_gate_mode == ReleaseGateMode.OFF:
        # Skip release gate — use the synthesis candidate as final answer
        final_answer = synthesis.candidate_markdown
        gate_executed = False
        gate_decision = ReleaseGateDecision.SKIPPED
        gate_summary = "Release gate skipped (mode=off)"
    else:
        gate_inv_id = make_invocation_id()
        emitter.emit(
            event_type=EventType.RELEASE_GATE_STARTED,
            phase=Phase.RELEASE_GATE,
            role=Role.MODERATOR,
            model=moderator,
            payload=ReleaseGateStartedPayload(
                invocation_id=gate_inv_id,
                mode=release_gate_mode,
                candidate_id=candidate_id,
                framing_version=1,
            ),
        )

        gate_response = await _invoke_structured(
            provider,
            moderator,
            build_release_gate_messages(
                user_prompt=prompt_text,
                framing=framing,
                candidate_markdown=synthesis.candidate_markdown,
                consensus_summary=consensus_summary,
                release_gate_mode=release_gate_mode,
            ),
        )
        gate_result = ReleaseGateResult.model_validate(gate_response.parsed)
        _record_usage(invocation_usages, gate_inv_id, moderator, Role.MODERATOR,
                      InvocationPurpose.RELEASE_GATE, gate_response.usage)

        final_answer = gate_result.final_answer_markdown
        gate_executed = True
        gate_decision = gate_result.decision
        gate_summary = gate_result.summary
        gate_minor_fixes = gate_result.minor_fixes_applied
        gate_blocking = gate_result.blocking_issues

        emitter.emit(
            event_type=EventType.RELEASE_GATE_COMPLETED,
            phase=Phase.RELEASE_GATE,
            role=Role.MODERATOR,
            model=moderator,
            payload=ReleaseGateCompletedPayload(
                invocation_id=gate_inv_id,
                candidate_id=candidate_id,
                framing_version=1,
                executed=True,
                decision=gate_decision,
                summary=gate_summary,
                minor_fixes_applied=gate_minor_fixes,
                blocking_issues=gate_blocking,
            ),
        )

    # ── 7. Finalization ─────────────────────────────────────────────────
    completed_at = utc_now_iso()

    # Compute total usage
    total_usage = _aggregate_usage(invocation_usages)

    # Compute duration
    total_duration_ms = duration_ms(started_at, completed_at)

    # Usage reported event
    emitter.emit(
        event_type=EventType.USAGE_REPORTED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=UsageReportedPayload(
            scope=UsageScope.RUN_TOTAL,
            usage=total_usage,
        ),
    )

    # run_completed
    emitter.emit(
        event_type=EventType.RUN_COMPLETED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=RunCompletedPayload(
            status=RunStatus.SUCCESS,
            rounds_completed=1,
            consensus_status=ConsensusStatus.REACHED,
            framing_version=1,
            final_answer_chars=len(final_answer),
            duration_ms=total_duration_ms,
        ),
    )

    # command_completed
    emitter.emit(
        event_type=EventType.COMMAND_COMPLETED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=CommandCompletedPayload(
            command_type="run",
            status="success",
        ),
    )

    # ── Build RunResult ─────────────────────────────────────────────────
    # Collect minor revision notes from reviews
    minor_revisions: list[str] = []
    for review in reviews:
        minor_revisions.extend(review.optional_improvements)

    return RunResult(
        run_id=emitter.run_id,
        status=RunStatus.SUCCESS,
        error=None,
        input=RunInputInfo(
            source="prompt",
            prompt_chars=len(prompt_text),
        ),
        models=RunModelsInfo(
            participants=participants,
            moderator=moderator,
        ),
        task_framing=RunTaskFramingInfo(
            task_type=framing.task_type,
            sensitivity=framing.sensitivity,
            objective=framing.objective,
            quality_criteria=framing.quality_criteria,
            aspects_to_cover=framing.aspects_to_cover,
            ambiguities=framing.ambiguities,
            assumptions=framing.assumptions,
            framing_version=1,
        ),
        consensus=RunConsensusInfo(
            status=ConsensusStatus.REACHED,
            rounds_completed=1,
            max_rounds=max_rounds,
            minor_revisions_applied=minor_revisions,
            blocking_issues_resolved=[],
            residual_disagreements=[],
        ),
        release_gate=RunReleaseGateInfo(
            mode=release_gate_mode,
            executed=gate_executed,
            decision=gate_decision,
            summary=gate_summary,
            minor_fixes_applied=gate_minor_fixes,
            blocking_issues=gate_blocking,
        ),
        final_answer=final_answer,
        usage=RunUsageInfo(
            per_invocation=invocation_usages,
            total=total_usage,
        ),
        timing=RunTimingInfo(
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=total_duration_ms,
        ),
    )


def _record_usage(
    usages: list[RunInvocationUsage],
    invocation_id: str,
    model: str,
    role: str,
    purpose: InvocationPurpose,
    usage: UsageSnapshot | None,
) -> None:
    """Record a single invocation's usage for the final RunResult."""
    usages.append(RunInvocationUsage(
        invocation_id=invocation_id,
        model=model,
        role=role,
        purpose=purpose,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
        cost_usd=usage.cost_usd if usage else None,
        is_complete=usage is not None,
    ))


def _aggregate_usage(usages: list[RunInvocationUsage]) -> UsageSnapshot:
    """Aggregate per-invocation usage into a total snapshot."""
    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    total_cost: float | None = None
    all_complete = True

    for u in usages:
        if u.prompt_tokens is not None:
            total_prompt += u.prompt_tokens
        else:
            all_complete = False
        if u.completion_tokens is not None:
            total_completion += u.completion_tokens
        else:
            all_complete = False
        if u.total_tokens is not None:
            total_tokens += u.total_tokens
        else:
            all_complete = False
        if u.cost_usd is not None:
            # Initialize on first non-None cost value
            if total_cost is None:
                total_cost = 0.0
            total_cost += u.cost_usd

    return UsageSnapshot(
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        total_tokens=total_tokens,
        cost_usd=total_cost,
        is_complete=all_complete,
    )
