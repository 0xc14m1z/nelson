"""Framing budget exhaustion tests (T-CONS-006).

Tests that a framing update in the last available round fails the run
with framing_update_budget_exhausted.
"""

import pytest

from nelson.protocols.enums import (
    EventType,
    RunStatus,
)
from nelson.protocols.events import TaskFramingUpdatedPayload
from nelson.providers.fake import FakeProvider

from .conftest import (
    contribution_response,
    framing_response,
    run_consensus_helper,
    synthesis_with_framing_update,
)


@pytest.mark.asyncio
async def test_framing_update_no_budget_fails() -> None:
    """T-CONS-006: framing update in the last round → run fails.

    With max_rounds=1, the first (and only) round's synthesis triggers
    a framing update. Since there are no remaining rounds for fresh
    contributions under the new framing, the run must fail with
    error code framing_update_budget_exhausted.
    """
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        # The only round's synthesis triggers a framing update
        synthesis_with_framing_update(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=1)

    assert result.status == RunStatus.FAILED
    assert result.error is not None
    assert result.error.code == "framing_update_budget_exhausted"

    # task_framing_updated should still be emitted before the failure
    framing_updated = [e for e in events if e.type == EventType.TASK_FRAMING_UPDATED]
    assert len(framing_updated) == 1
    assert isinstance(framing_updated[0].payload, TaskFramingUpdatedPayload)

    # run_failed should be emitted
    run_failed = [e for e in events if e.type == EventType.RUN_FAILED]
    assert len(run_failed) == 1

    # command_failed should be terminal
    cmd_failed = [e for e in events if e.type == EventType.COMMAND_FAILED]
    assert len(cmd_failed) == 1
