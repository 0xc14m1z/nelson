"""Consensus orchestrator — multi-round consensus loop.

Coordinates the multi-model consensus workflow:
task framing → contributions → synthesis → review → release gate.

Phase 7 extends Phase 6 with:
- Multi-round loop: major_revise/reject trigger new rounds
- Framing updates: moderator can update framing mid-run, invalidating candidates
- Partial consensus: max_rounds exhaustion produces partial results
- Framing budget exhaustion: update in last round fails the run
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
    ErrorObject,
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
    ErrorCode,
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
    CandidateUpdatedPayload,
    CommandCompletedPayload,
    CommandFailedPayload,
    CommandReceivedPayload,
    ConsensusPartialPayload,
    ConsensusPendingPayload,
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
    RunFailedPayload,
    RunStartedPayload,
    TaskFramingCompletedPayload,
    TaskFramingStartedPayload,
    TaskFramingUpdatedPayload,
    UsageReportedPayload,
)
from nelson.protocols.results import (
    RunConsensusInfo,
    RunInputInfo,
    RunInvocationUsage,
    RunModelsInfo,
    RunReleaseGateInfo,
    RunResult,
    RunResultError,
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


def _tally_reviews(reviews: list[ReviewResult]) -> tuple[dict[ReviewDecision, int], bool]:
    """Count review decisions and detect blocking reviews in a single pass.

    Returns (counts_by_decision, has_blocking). Keyed by ReviewDecision enum
    so the dict stays in sync if new decisions are added.
    """
    counts: dict[ReviewDecision, int] = dict.fromkeys(ReviewDecision, 0)
    has_blocking = False
    for r in reviews:
        counts[r.decision] += 1
        if r.decision in (ReviewDecision.MAJOR_REVISE, ReviewDecision.REJECT):
            has_blocking = True
    return counts, has_blocking


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
    """Execute a multi-round consensus run.

    Coordinates all consensus phases and emits events via the emitter.
    Returns a fully populated RunResult.

    Supports multi-round consensus (major_revise/reject trigger new rounds),
    material framing updates (invalidate current candidate, start fresh round),
    partial consensus (max_rounds exhaustion), and framing budget exhaustion.
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
            streaming=False,
        ),
    )

    framing_resp = await _invoke_structured(
        provider,
        moderator,
        build_framing_messages(
            user_prompt=prompt_text,
            max_rounds=max_rounds,
            release_gate_mode=release_gate_mode,
        ),
    )
    framing = TaskFramingResult.model_validate(framing_resp.parsed)
    _record_usage(invocation_usages, framing_inv_id, moderator, Role.MODERATOR,
                  InvocationPurpose.TASK_FRAMING, framing_resp.usage)

    framing_version = 1
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
            framing_version=framing_version,
        ),
    )

    # ── 2. Initial Participant Contributions (parallel) ──────────────────
    contributions = await _gather_contributions(
        provider=provider,
        participants=participants,
        prompt_text=prompt_text,
        framing=framing,
        framing_version=framing_version,
        purpose=InvocationPurpose.INITIAL_CONTRIBUTION,
        emitter=emitter,
        invocation_usages=invocation_usages,
    )

    # ── 3. Multi-Round Consensus Loop ───────────────────────────────────
    round_number = 0
    consensus_reached = False
    consensus_summary = ""
    reviews: list[ReviewResult] = []  # overwritten each round; final value used post-loop
    all_blocking_resolved: list[str] = []
    candidate_id = ""
    synthesis: CandidateSynthesisResult | None = None
    # Track whether contributions need to be refreshed (after framing update)
    needs_fresh_contributions = False

    while round_number < max_rounds:
        round_number += 1

        # If framing was updated in the previous round, gather fresh contributions
        if needs_fresh_contributions:
            contributions = await _gather_contributions(
                provider=provider,
                participants=participants,
                prompt_text=prompt_text,
                framing=framing,
                framing_version=framing_version,
                purpose=InvocationPurpose.REFRAMED_CONTRIBUTION,
                emitter=emitter,
                invocation_usages=invocation_usages,
            )
            needs_fresh_contributions = False

        # ── Candidate Synthesis ──────────────────────────────────────────
        # Determine candidate source based on round context
        if round_number == 1:
            source = CandidateSource.INITIAL_SYNTHESIS
        else:
            source = CandidateSource.MAJOR_REVISE_CYCLE

        previous_candidate_id = candidate_id if round_number > 1 else None

        synthesis_inv_id = make_invocation_id()
        emitter.emit(
            event_type=EventType.MODEL_STARTED,
            phase=Phase.CANDIDATE_SYNTHESIS,
            role=Role.MODERATOR,
            model=moderator,
            payload=ModelStartedPayload(
                invocation_id=synthesis_inv_id,
                purpose=InvocationPurpose.CANDIDATE_SYNTHESIS,
                framing_version=framing_version,
                schema_name=CandidateSynthesisResult.__name__,
                streaming=False,
            ),
        )

        synthesis_resp = await _invoke_structured(
            provider,
            moderator,
            build_synthesis_messages(
                user_prompt=prompt_text,
                framing=framing,
                contributions=contributions,
                round_number=round_number,
            ),
        )
        synthesis = CandidateSynthesisResult.model_validate(synthesis_resp.parsed)
        _record_usage(invocation_usages, synthesis_inv_id, moderator, Role.MODERATOR,
                      InvocationPurpose.CANDIDATE_SYNTHESIS, synthesis_resp.usage)

        emitter.emit(
            event_type=EventType.MODEL_COMPLETED,
            phase=Phase.CANDIDATE_SYNTHESIS,
            role=Role.MODERATOR,
            model=moderator,
            payload=ModelCompletedPayload(
                invocation_id=synthesis_inv_id,
                purpose=InvocationPurpose.CANDIDATE_SYNTHESIS,
                framing_version=framing_version,
                finish_reason=FinishReason.STOP,
                output_format=OutputFormat.STRUCTURED,
            ),
        )

        candidate_id = make_candidate_id()

        # Emit candidate_created or candidate_updated depending on round
        if previous_candidate_id is None:
            emitter.emit(
                event_type=EventType.CANDIDATE_CREATED,
                phase=Phase.CANDIDATE_SYNTHESIS,
                role=Role.MODERATOR,
                model=moderator,
                payload=CandidateCreatedPayload(
                    candidate_id=candidate_id,
                    framing_version=framing_version,
                    source=source,
                    text=synthesis.candidate_markdown,
                    summary=synthesis.summary,
                    excerpt_count=len(synthesis.relevant_excerpt_labels),
                ),
            )
        else:
            emitter.emit(
                event_type=EventType.CANDIDATE_UPDATED,
                phase=Phase.CANDIDATE_SYNTHESIS,
                role=Role.MODERATOR,
                model=moderator,
                payload=CandidateUpdatedPayload(
                    candidate_id=candidate_id,
                    previous_candidate_id=previous_candidate_id,
                    framing_version=framing_version,
                    source=source,
                    text=synthesis.candidate_markdown,
                    summary=synthesis.summary,
                ),
            )

        # ── Check for framing update from synthesis ──────────────────────
        if synthesis.framing_update is not None:
            # Material framing change — invalidate this candidate
            old_framing_version = framing_version
            framing_version += 1
            framing = synthesis.framing_update

            emitter.emit(
                event_type=EventType.TASK_FRAMING_UPDATED,
                phase=Phase.TASK_FRAMING,
                role=Role.MODERATOR,
                model=moderator,
                round_number=round_number,
                payload=TaskFramingUpdatedPayload(
                    task_type=framing.task_type,
                    sensitivity=framing.sensitivity,
                    objective=framing.objective,
                    quality_criteria=framing.quality_criteria,
                    aspects_to_cover=framing.aspects_to_cover,
                    ambiguities=framing.ambiguities,
                    assumptions=framing.assumptions,
                    framing_version=framing_version,
                    previous_framing_version=old_framing_version,
                    effective_from_round=round_number + 1,
                    invalidated_candidate_id=candidate_id,
                    update_reason=synthesis.summary,
                ),
            )

            # Round completed with candidate invalidated — no review executed
            emitter.emit(
                event_type=EventType.ROUND_COMPLETED,
                phase=Phase.PARTICIPANT_REVIEW,
                role=Role.SYSTEM,
                round_number=round_number,
                payload=RoundCompletedPayload(
                    round=round_number,
                    candidate_id=candidate_id,
                    framing_version=old_framing_version,
                    review_executed=False,
                    candidate_invalidated_by_framing_update=True,
                    will_continue=round_number < max_rounds,
                ),
            )

            # Check framing budget: if no rounds remain, fail the run
            if round_number >= max_rounds:
                return _build_failed_result(
                    emitter=emitter,
                    error_code=ErrorCode.FRAMING_UPDATE_BUDGET_EXHAUSTED,
                    error_message=(
                        "Framing update occurred in the last available round; "
                        "no budget remains for fresh contributions"
                    ),
                    phase=Phase.TASK_FRAMING,
                    framing=framing,
                    framing_version=framing_version,
                    round_number=round_number,
                    max_rounds=max_rounds,
                    participants=participants,
                    moderator=moderator,
                    prompt_text=prompt_text,
                    release_gate_mode=release_gate_mode,
                    invocation_usages=invocation_usages,
                    started_at=started_at,
                )

            # Next round needs fresh contributions under the updated framing
            needs_fresh_contributions = True
            continue

        # ── Round started (with review) ──────────────────────────────────
        emitter.emit(
            event_type=EventType.ROUND_STARTED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.SYSTEM,
            round_number=round_number,
            payload=RoundStartedPayload(
                round=round_number,
                candidate_id=candidate_id,
                framing_version=framing_version,
                target_participant_count=len(participants),
            ),
        )

        # ── Participant Reviews ──────────────────────────────────────────
        reviews = await _gather_reviews(
            provider=provider,
            participants=participants,
            prompt_text=prompt_text,
            framing=framing,
            framing_version=framing_version,
            candidate_id=candidate_id,
            candidate_markdown=synthesis.candidate_markdown,
            synthesis_summary=synthesis.summary,
            contributions=contributions,
            round_number=round_number,
            emitter=emitter,
            invocation_usages=invocation_usages,
        )
        counts, blocking = _tally_reviews(reviews)

        # Collect blocking issue summaries for this round
        round_blocking_summaries: list[str] = []
        round_minor_summaries: list[str] = []
        for r in reviews:
            round_blocking_summaries.extend(r.blocking_issues)
            round_minor_summaries.extend(r.optional_improvements)

        emitter.emit(
            event_type=EventType.REVIEW_COMPLETED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.SYSTEM,
            round_number=round_number,
            payload=ReviewCompletedPayload(
                candidate_id=candidate_id,
                framing_version=framing_version,
                reviewer_count=len(participants),
                approve_count=counts[ReviewDecision.APPROVE],
                minor_revise_count=counts[ReviewDecision.MINOR_REVISE],
                major_revise_count=counts[ReviewDecision.MAJOR_REVISE],
                reject_count=counts[ReviewDecision.REJECT],
                blocking_issue_summaries=round_blocking_summaries,
                minor_improvement_summaries=round_minor_summaries,
            ),
        )

        if blocking:
            # Consensus not reached — emit consensus_pending
            emitter.emit(
                event_type=EventType.CONSENSUS_PENDING,
                phase=Phase.PARTICIPANT_REVIEW,
                role=Role.SYSTEM,
                round_number=round_number,
                payload=ConsensusPendingPayload(
                    candidate_id=candidate_id,
                    reviewer_count=len(participants),
                    blocking_review_count=(
                        counts[ReviewDecision.MAJOR_REVISE] + counts[ReviewDecision.REJECT]
                    ),
                    minor_revise_count=counts[ReviewDecision.MINOR_REVISE],
                    major_revise_count=counts[ReviewDecision.MAJOR_REVISE],
                    reject_count=counts[ReviewDecision.REJECT],
                    summary=(
                        f"{counts[ReviewDecision.MAJOR_REVISE] + counts[ReviewDecision.REJECT]}"
                        " blocking issue(s) remain"
                    ),
                ),
            )

            will_continue = round_number < max_rounds

            emitter.emit(
                event_type=EventType.ROUND_COMPLETED,
                phase=Phase.PARTICIPANT_REVIEW,
                role=Role.SYSTEM,
                round_number=round_number,
                payload=RoundCompletedPayload(
                    round=round_number,
                    candidate_id=candidate_id,
                    framing_version=framing_version,
                    review_executed=True,
                    approve_count=counts[ReviewDecision.APPROVE],
                    minor_revise_count=counts[ReviewDecision.MINOR_REVISE],
                    major_revise_count=counts[ReviewDecision.MAJOR_REVISE],
                    reject_count=counts[ReviewDecision.REJECT],
                    will_continue=will_continue,
                ),
            )

            if not will_continue:
                # Max rounds exhausted — partial consensus
                break

            # Track resolved blocking issues for the result
            all_blocking_resolved.extend(round_blocking_summaries)
            continue

        # ── Consensus reached ────────────────────────────────────────────
        consensus_reached = True

        if counts[ReviewDecision.MINOR_REVISE] > 0:
            consensus_summary = (
                f"{counts[ReviewDecision.APPROVE]} approved, "
                f"{counts[ReviewDecision.MINOR_REVISE]} requested minor revisions"
            )
        else:
            consensus_summary = "All participants approved the candidate"

        emitter.emit(
            event_type=EventType.CONSENSUS_REACHED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.SYSTEM,
            round_number=round_number,
            payload=ConsensusReachedPayload(
                candidate_id=candidate_id,
                reviewer_count=len(participants),
                approve_count=counts[ReviewDecision.APPROVE],
                minor_revise_count=counts[ReviewDecision.MINOR_REVISE],
                major_revise_count=0,
                reject_count=0,
                summary=consensus_summary,
            ),
        )

        emitter.emit(
            event_type=EventType.ROUND_COMPLETED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.SYSTEM,
            round_number=round_number,
            payload=RoundCompletedPayload(
                round=round_number,
                candidate_id=candidate_id,
                framing_version=framing_version,
                review_executed=True,
                approve_count=counts[ReviewDecision.APPROVE],
                minor_revise_count=counts[ReviewDecision.MINOR_REVISE],
                major_revise_count=0,
                reject_count=0,
                will_continue=False,
            ),
        )
        break

    assert synthesis is not None  # at least one round always executes

    # ── Handle partial consensus (max rounds exhausted) ──────────────────
    unique_residual: list[str] = []
    if not consensus_reached:
        # Collect residual disagreements from the final round's blocking reviews.
        # Only the last round matters — earlier rounds' issues were addressed.
        seen: set[str] = set()
        for r in reviews:
            if r.decision in (ReviewDecision.MAJOR_REVISE, ReviewDecision.REJECT):
                for issue in r.blocking_issues:
                    if issue not in seen:
                        seen.add(issue)
                        unique_residual.append(issue)
                if r.summary and r.summary not in seen:
                    seen.add(r.summary)
                    unique_residual.append(r.summary)

        emitter.emit(
            event_type=EventType.CONSENSUS_PARTIAL,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.SYSTEM,
            payload=ConsensusPartialPayload(
                candidate_id=candidate_id,
                reason="max_rounds_exhausted",
                unresolved_issues=unique_residual,
            ),
        )

        consensus_summary = f"Partial consensus after {round_number} rounds"
        consensus_status = ConsensusStatus.PARTIAL
        run_status = RunStatus.PARTIAL
    else:
        consensus_status = ConsensusStatus.REACHED
        run_status = RunStatus.SUCCESS

    # ── Release Gate ─────────────────────────────────────────────────────
    final_answer: str
    gate_executed: bool
    gate_decision: ReleaseGateDecision
    gate_summary: str
    gate_minor_fixes: list[str] = []
    gate_blocking: list[str] = []

    if release_gate_mode == ReleaseGateMode.OFF or not consensus_reached:
        # Skip release gate — use the synthesis candidate as final answer
        # Also skip for partial consensus (no point in gating an incomplete result)
        final_answer = synthesis.candidate_markdown
        gate_executed = False
        gate_decision = ReleaseGateDecision.SKIPPED
        gate_summary = (
            "Release gate skipped (mode=off)"
            if release_gate_mode == ReleaseGateMode.OFF
            else "Release gate skipped (partial consensus)"
        )
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
                framing_version=framing_version,
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
                framing_version=framing_version,
                executed=True,
                decision=gate_decision,
                summary=gate_summary,
                minor_fixes_applied=gate_minor_fixes,
                blocking_issues=gate_blocking,
            ),
        )

    # ── Finalization ─────────────────────────────────────────────────────
    completed_at = utc_now_iso()
    total_usage = _aggregate_usage(invocation_usages)
    total_duration_ms = duration_ms(started_at, completed_at)

    emitter.emit(
        event_type=EventType.USAGE_REPORTED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=UsageReportedPayload(
            scope=UsageScope.RUN_TOTAL,
            usage=total_usage,
        ),
    )

    emitter.emit(
        event_type=EventType.RUN_COMPLETED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=RunCompletedPayload(
            status=run_status,
            rounds_completed=round_number,
            consensus_status=consensus_status,
            framing_version=framing_version,
            final_answer_chars=len(final_answer),
            duration_ms=total_duration_ms,
        ),
    )

    # Terminal command event depends on run status
    if run_status == RunStatus.SUCCESS:
        emitter.emit(
            event_type=EventType.COMMAND_COMPLETED,
            phase=Phase.COMMAND,
            role=Role.SYSTEM,
            payload=CommandCompletedPayload(
                command_type="run",
                status="success",
            ),
        )
    else:
        # Partial consensus still counts as a completed command (not failed)
        emitter.emit(
            event_type=EventType.COMMAND_COMPLETED,
            phase=Phase.COMMAND,
            role=Role.SYSTEM,
            payload=CommandCompletedPayload(
                command_type="run",
                status="partial",
            ),
        )

    # ── Build RunResult ─────────────────────────────────────────────────
    # Collect minor revision suggestions from the final round's reviews
    minor_revisions: list[str] = []
    for review in reviews:
        minor_revisions.extend(review.optional_improvements)

    return RunResult(
        run_id=emitter.run_id,
        status=run_status,
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
            framing_version=framing_version,
        ),
        consensus=RunConsensusInfo(
            status=consensus_status,
            rounds_completed=round_number,
            max_rounds=max_rounds,
            minor_revisions_applied=minor_revisions,
            blocking_issues_resolved=all_blocking_resolved,
            residual_disagreements=unique_residual if not consensus_reached else [],
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


# ── Extracted helpers ────────────────────────────────────────────────────


async def _gather_contributions(
    *,
    provider: Provider,
    participants: list[str],
    prompt_text: str,
    framing: TaskFramingResult,
    framing_version: int,
    purpose: InvocationPurpose,
    emitter: EventEmitter,
    invocation_usages: list[RunInvocationUsage],
) -> list[ParticipantContribution]:
    """Invoke all participants in parallel and collect contributions.

    Emits MODEL_STARTED before gather and MODEL_COMPLETED after,
    preserving deterministic event ordering (EVENT_SCHEMA §5).
    """
    inv_ids: list[str] = []
    for participant in participants:
        inv_id = make_invocation_id()
        inv_ids.append(inv_id)
        emitter.emit(
            event_type=EventType.MODEL_STARTED,
            phase=Phase.PARTICIPANT_GENERATION,
            role=Role.PARTICIPANT,
            model=participant,
            payload=ModelStartedPayload(
                invocation_id=inv_id,
                purpose=purpose,
                framing_version=framing_version,
                schema_name=ParticipantContribution.__name__,
                streaming=False,
            ),
        )

    responses = await asyncio.gather(*(
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
        participants, inv_ids, responses, strict=True,
    ):
        contribution = ParticipantContribution.model_validate(response.parsed)
        contributions.append(contribution)
        _record_usage(invocation_usages, inv_id, participant, Role.PARTICIPANT,
                      purpose, response.usage)
        emitter.emit(
            event_type=EventType.MODEL_COMPLETED,
            phase=Phase.PARTICIPANT_GENERATION,
            role=Role.PARTICIPANT,
            model=participant,
            payload=ModelCompletedPayload(
                invocation_id=inv_id,
                purpose=purpose,
                framing_version=framing_version,
                finish_reason=FinishReason.STOP,
                output_format=OutputFormat.STRUCTURED,
            ),
        )

    return contributions


async def _gather_reviews(
    *,
    provider: Provider,
    participants: list[str],
    prompt_text: str,
    framing: TaskFramingResult,
    framing_version: int,
    candidate_id: str,
    candidate_markdown: str,
    synthesis_summary: str,
    contributions: list[ParticipantContribution],
    round_number: int,
    emitter: EventEmitter,
    invocation_usages: list[RunInvocationUsage],
) -> list[ReviewResult]:
    """Invoke all participant reviews in parallel and collect results.

    Emits review_started, MODEL_STARTED events before gather,
    and MODEL_COMPLETED events after, preserving deterministic ordering.
    """
    emitter.emit(
        event_type=EventType.REVIEW_STARTED,
        phase=Phase.PARTICIPANT_REVIEW,
        role=Role.SYSTEM,
        round_number=round_number,
        payload=ReviewStartedPayload(
            candidate_id=candidate_id,
            framing_version=framing_version,
            target_participant_count=len(participants),
        ),
    )

    inv_ids: list[str] = []
    for participant in participants:
        inv_id = make_invocation_id()
        inv_ids.append(inv_id)
        emitter.emit(
            event_type=EventType.MODEL_STARTED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.PARTICIPANT,
            model=participant,
            round_number=round_number,
            payload=ModelStartedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.CANDIDATE_REVIEW,
                framing_version=framing_version,
                schema_name=ReviewResult.__name__,
                streaming=False,
            ),
        )

    responses = await asyncio.gather(*(
        _invoke_structured(
            provider,
            participant,
            build_review_messages(
                user_prompt=prompt_text,
                framing=framing,
                candidate_markdown=candidate_markdown,
                synthesis_summary=synthesis_summary,
                contributions=contributions,
                participant_model=participant,
            ),
        )
        for participant in participants
    ))

    reviews: list[ReviewResult] = []
    for participant, inv_id, response in zip(
        participants, inv_ids, responses, strict=True,
    ):
        review = ReviewResult.model_validate(response.parsed)
        reviews.append(review)
        _record_usage(invocation_usages, inv_id, participant, Role.PARTICIPANT,
                      InvocationPurpose.CANDIDATE_REVIEW, response.usage)
        emitter.emit(
            event_type=EventType.MODEL_COMPLETED,
            phase=Phase.PARTICIPANT_REVIEW,
            role=Role.PARTICIPANT,
            model=participant,
            round_number=round_number,
            payload=ModelCompletedPayload(
                invocation_id=inv_id,
                purpose=InvocationPurpose.CANDIDATE_REVIEW,
                framing_version=framing_version,
                finish_reason=FinishReason.STOP,
                output_format=OutputFormat.STRUCTURED,
            ),
        )

    return reviews


def _build_failed_result(
    *,
    emitter: EventEmitter,
    error_code: ErrorCode,
    error_message: str,
    phase: Phase,
    framing: TaskFramingResult,
    framing_version: int,
    round_number: int,
    max_rounds: int,
    participants: list[str],
    moderator: str,
    prompt_text: str,
    release_gate_mode: ReleaseGateMode,
    invocation_usages: list[RunInvocationUsage],
    started_at: str,
) -> RunResult:
    """Emit failure events and build a failed RunResult."""
    completed_at = utc_now_iso()
    total_usage = _aggregate_usage(invocation_usages)
    total_duration_ms = duration_ms(started_at, completed_at)

    error = ErrorObject(
        code=error_code,
        message=error_message,
        retryable=False,
    )

    # Emit usage, run_failed, command_failed
    emitter.emit(
        event_type=EventType.USAGE_REPORTED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=UsageReportedPayload(
            scope=UsageScope.RUN_TOTAL,
            usage=total_usage,
        ),
    )

    emitter.emit(
        event_type=EventType.RUN_FAILED,
        phase=Phase.FINALIZATION,
        role=Role.SYSTEM,
        payload=RunFailedPayload(
            status="failed",
            framing_version=framing_version,
            error=error,
        ),
    )

    emitter.emit(
        event_type=EventType.COMMAND_FAILED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=CommandFailedPayload(
            command_type="run",
            error=error,
        ),
    )

    return RunResult(
        run_id=emitter.run_id,
        status=RunStatus.FAILED,
        error=RunResultError(
            code=error_code,
            message=error_message,
            retryable=False,
            phase=phase,
        ),
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
            framing_version=framing_version,
        ),
        consensus=RunConsensusInfo(
            status=ConsensusStatus.FAILED,
            rounds_completed=round_number,
            max_rounds=max_rounds,
        ),
        release_gate=RunReleaseGateInfo(
            mode=release_gate_mode,
            executed=False,
            decision=ReleaseGateDecision.SKIPPED,
            summary="Release gate skipped (run failed)",
        ),
        final_answer=None,
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
