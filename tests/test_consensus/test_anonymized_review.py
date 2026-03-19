"""Anonymized review context tests.

Verifies that participant reviews receive labeled excerpts (response_a,
response_b, etc.) instead of real model identifiers, per PROMPT_SPEC §7.2.
"""

import pytest

from nelson.prompts.labels import label_contributions
from nelson.protocols.domain import (
    FramingFeedback,
    ParticipantContribution,
)
from nelson.protocols.enums import FramingFeedbackStatus


@pytest.mark.asyncio
async def test_review_context_uses_labels_not_model_ids() -> None:
    """Review inputs use response_a/response_b labels, not model IDs.

    The label_contributions() utility must produce anonymized labels
    that do not leak which model produced which contribution.
    """
    contributions = [
        ParticipantContribution(
            answer_markdown="First participant's answer about the topic.",
            framing_feedback=FramingFeedback(status=FramingFeedbackStatus.ACCEPT),
        ),
        ParticipantContribution(
            answer_markdown="Second participant's answer about the topic.",
            framing_feedback=FramingFeedback(status=FramingFeedbackStatus.ACCEPT),
        ),
    ]

    labeled = label_contributions(contributions)

    assert len(labeled) == 2
    # Labels should use response_a/response_b pattern, not model IDs
    assert labeled[0].startswith("response_a:")
    assert labeled[1].startswith("response_b:")
    # The labeling function must not inject model identifiers anywhere
    for label_text in labeled:
        assert "gpt" not in label_text.lower()
        assert "claude" not in label_text.lower()
        assert "openai" not in label_text.lower()
        assert "anthropic" not in label_text.lower()
