"""Application protocol shape — CommandExecution interface."""

from collections.abc import AsyncIterator
from typing import Protocol

from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import CommandResult


class CommandExecution(Protocol):
    """The shape of a dispatched command's execution.

    Implementors emit a stream of typed events during execution and produce
    a terminal result when the command completes.
    """

    @property
    def events(self) -> AsyncIterator[ApplicationEvent]:
        """Async stream of events emitted during execution."""
        ...

    async def result(self) -> CommandResult | None:
        """Terminal result, or ``None`` if the command produced no result."""
        ...
