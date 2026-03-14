"""JSON output mode tests (T-OUT-002).

Verifies that --json mode outputs exactly one JSON object on stdout
with no intermixed progress text.
"""

import json

from nelson.cli.render_json import render_json
from nelson.providers.fake import FakeProvider
from tests.test_consensus.conftest import run_happy_path


async def test_json_mode_outputs_single_json_object(
    happy_path_provider: FakeProvider,
) -> None:
    """stdout must be exactly one parseable JSON document."""
    _events, result = await run_happy_path(happy_path_provider)
    stdout = render_json(result)
    # Must parse as JSON
    parsed = json.loads(stdout)
    assert isinstance(parsed, dict)
    # Must have required top-level fields
    assert "run_id" in parsed
    assert "status" in parsed
    assert "final_answer" in parsed


async def test_json_mode_no_progress_on_stdout(
    happy_path_provider: FakeProvider,
) -> None:
    """JSON output must not contain non-JSON progress text on stdout."""
    _events, result = await run_happy_path(happy_path_provider)
    stdout = render_json(result)
    # The entire stdout must be valid JSON — no extra text before or after
    stripped = stdout.strip()
    assert stripped.startswith("{")
    assert stripped.endswith("}")
    # Must be parseable as a single JSON object
    json.loads(stripped)
