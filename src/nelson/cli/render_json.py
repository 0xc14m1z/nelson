"""JSON output renderer (CLI_SPEC §8).

Renders a RunResult as a single JSON object on stdout.
No progress text, no extra output — just the JSON.
"""

from nelson.protocols.results import RunResult


def render_json(result: RunResult) -> str:
    """Render the RunResult as a single indented JSON string."""
    return result.model_dump_json(indent=2)
