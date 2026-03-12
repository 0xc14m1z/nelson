"""Application protocol shape — CommandExecution interface."""

from collections.abc import AsyncIterator
from typing import Protocol

from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import CommandResult


class CommandExecution(Protocol):
    """The conceptual shape of a dispatched command's execution."""

    @property
    def events(self) -> AsyncIterator[ApplicationEvent]: ...

    async def result(self) -> CommandResult | None: ...
