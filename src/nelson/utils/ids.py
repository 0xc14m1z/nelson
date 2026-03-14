"""Prefixed unique ID generation for Nelson domain objects.

Each domain entity type has its own prefix to make IDs self-describing
in logs, events, and the ``--json`` output (EVENT_SCHEMA §1.1).
"""

import uuid


def _make_id(prefix: str) -> str:
    """Generate a prefixed unique ID using UUID4 hex truncated to 12 chars.

    12 hex chars = 48 bits of entropy (~280 trillion values). Collision
    probability stays negligible for the expected scale of a single CLI
    session (hundreds of IDs at most). The short form keeps event logs
    and JSON output readable.
    """
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def make_run_id() -> str:
    """Generate a unique run identifier with ``run_`` prefix."""
    return _make_id("run_")


def make_command_id() -> str:
    """Generate a unique command identifier with ``cmd_`` prefix."""
    return _make_id("cmd_")


def make_invocation_id() -> str:
    """Generate a unique invocation identifier with ``inv_`` prefix."""
    return _make_id("inv_")


def make_candidate_id() -> str:
    """Generate a unique candidate identifier with ``cand_`` prefix."""
    return _make_id("cand_")
