"""JSONL output mode tests (T-OUT-003).

Verifies that --jsonl mode outputs one JSON object per line on stdout
with monotonically increasing sequence numbers.
"""

import json

from nelson.cli.render_jsonl import render_jsonl
from nelson.providers.fake import FakeProvider
from tests.test_consensus.conftest import run_happy_path


async def test_jsonl_mode_outputs_json_lines(
    happy_path_provider: FakeProvider,
) -> None:
    """Every line of stdout must parse as valid JSON."""
    events, _result = await run_happy_path(happy_path_provider)
    stdout = render_jsonl(events)
    lines = [line for line in stdout.strip().split("\n") if line.strip()]
    assert len(lines) > 0, "JSONL output must have at least one line"
    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert isinstance(parsed, dict), f"Line {i} is not a JSON object"
        assert "type" in parsed, f"Line {i} missing 'type' field"


async def test_jsonl_events_have_monotonic_sequence(
    happy_path_provider: FakeProvider,
) -> None:
    """sequence field must be 1, 2, 3, ... across all JSONL lines."""
    events, _result = await run_happy_path(happy_path_provider)
    stdout = render_jsonl(events)
    lines = [line for line in stdout.strip().split("\n") if line.strip()]
    sequences = [json.loads(line)["sequence"] for line in lines]
    expected = list(range(1, len(sequences) + 1))
    assert sequences == expected
