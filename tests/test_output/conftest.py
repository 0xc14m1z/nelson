"""Shared fixtures for output rendering tests.

Re-exports fixtures from the consensus test suite so output tests
can use the same fake provider data.
"""

from tests.test_consensus.conftest import happy_path_provider

__all__ = ["happy_path_provider"]
