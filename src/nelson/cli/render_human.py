"""Human output renderer (CLI_SPEC §7).

Renders the final answer on stdout and progress on stderr.
Model identities are not shown by default.
"""

from nelson.protocols.enums import ConsensusStatus, EventType
from nelson.protocols.events import ApplicationEvent, RoundStartedPayload
from nelson.protocols.results import RunResult


def render_human(
    events: list[ApplicationEvent],
    result: RunResult,
) -> tuple[str, str]:
    """Render for human consumption.

    Returns:
        A tuple of (stdout_text, stderr_text).
        stdout contains the final answer and consensus status.
        stderr contains progress information from events.
    """
    # ── stdout: final answer + consensus status ────────────────────────
    stdout_parts: list[str] = []
    if result.final_answer:
        stdout_parts.append(result.final_answer)

    # Consensus status line
    status = result.consensus.status
    if status == ConsensusStatus.REACHED:
        stdout_parts.append("\nConsensus reached.")
    elif status == ConsensusStatus.PARTIAL:
        stdout_parts.append("\nPartial consensus (max rounds exhausted).")
        if result.consensus.residual_disagreements:
            for d in result.consensus.residual_disagreements:
                stdout_parts.append(f"  - {d}")

    # Minor revisions note
    if result.consensus.minor_revisions_applied:
        stdout_parts.append("\nMinor revisions applied:")
        for rev in result.consensus.minor_revisions_applied:
            stdout_parts.append(f"  - {rev}")

    stdout = "\n".join(stdout_parts)

    # ── stderr: progress from events ───────────────────────────────────
    stderr_parts: list[str] = []
    for event in events:
        if event.type == EventType.TASK_FRAMING_COMPLETED:
            stderr_parts.append("Task framing complete.")
        elif event.type == EventType.MODEL_COMPLETED:
            stderr_parts.append("Model invocation complete.")
        elif event.type == EventType.ROUND_STARTED:
            payload = event.payload
            if isinstance(payload, RoundStartedPayload):
                stderr_parts.append(
                    f"Round {payload.round}/{result.consensus.max_rounds} started."
                )
        elif event.type == EventType.CONSENSUS_REACHED:
            stderr_parts.append("Consensus reached.")
        elif event.type == EventType.RELEASE_GATE_COMPLETED:
            stderr_parts.append("Release gate complete.")

    stderr = "\n".join(stderr_parts)
    return stdout, stderr
