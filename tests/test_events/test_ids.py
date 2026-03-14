"""ID generation tests.

Verifies that each ID type has the correct prefix and that generated IDs
are unique.
"""

from nelson.utils.ids import (
    make_candidate_id,
    make_command_id,
    make_invocation_id,
    make_run_id,
)


def test_run_id_prefix() -> None:
    """Run IDs must start with ``run_``."""
    assert make_run_id().startswith("run_")


def test_command_id_prefix() -> None:
    """Command IDs must start with ``cmd_``."""
    assert make_command_id().startswith("cmd_")


def test_invocation_id_prefix() -> None:
    """Invocation IDs must start with ``inv_``."""
    assert make_invocation_id().startswith("inv_")


def test_candidate_id_prefix() -> None:
    """Candidate IDs must start with ``cand_``."""
    assert make_candidate_id().startswith("cand_")


def test_ids_are_unique() -> None:
    """Generate 100 IDs of each type, assert no duplicates across all types."""
    all_ids: set[str] = set()
    generators = [make_run_id, make_command_id, make_invocation_id, make_candidate_id]
    for gen in generators:
        for _ in range(100):
            id_ = gen()
            assert id_ not in all_ids, f"Duplicate ID: {id_}"
            all_ids.add(id_)
    # 4 generators * 100 each = 400 unique IDs
    assert len(all_ids) == 400
