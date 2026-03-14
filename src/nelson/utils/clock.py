"""UTC timestamp helper.

Centralizes timestamp generation so all events use the same format
(ISO 8601 UTC, EVENT_SCHEMA §1.1).
"""

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
