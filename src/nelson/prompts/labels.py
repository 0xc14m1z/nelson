"""Shared labeling utilities for prompt construction.

Contributions are labeled as response_a, response_b, etc. per
PROMPT_SPEC 7.2 for anonymized participant references.
"""

from nelson.protocols.domain import ParticipantContribution


def label_contributions(contributions: list[ParticipantContribution]) -> list[str]:
    """Label contributions as response_a, response_b, etc. for prompt embedding."""
    labeled: list[str] = []
    for i, contrib in enumerate(contributions):
        label = chr(ord("a") + i)
        labeled.append(f"response_{label}: {contrib.model_dump_json()}")
    return labeled
