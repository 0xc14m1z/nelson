"""JSONL output renderer (CLI_SPEC §9).

Renders events as one JSON object per line on stdout.
Each line is a complete serialized ApplicationEvent.
"""

from nelson.protocols.events import ApplicationEvent


def render_jsonl(events: list[ApplicationEvent]) -> str:
    """Render events as newline-delimited JSON (JSONL).

    Each event is serialized as a single JSON line.
    Events appear in their natural sequence order.
    """
    lines = [event.model_dump_json() for event in events]
    return "\n".join(lines) + "\n" if lines else ""
