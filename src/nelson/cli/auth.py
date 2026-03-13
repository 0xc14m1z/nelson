"""Auth command group — save, check, and clear OpenRouter API keys."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from nelson.core.dispatcher import AuthCommandExecution, dispatch
from nelson.protocols.commands import AuthClearCommand, AuthSetCommand, AuthStatusCommand
from nelson.protocols.results import AuthClearResult, AuthSetResult, AuthStatusResult, CommandResult

app = typer.Typer(help="Manage OpenRouter API key.")


def _config_dir() -> Path:
    """Return the effective config directory (respects HOME override).

    Called at runtime (not import time) so that monkeypatching HOME
    in tests is reflected correctly.
    """
    return Path.home() / ".nelson"


async def _drain_and_result(execution: AuthCommandExecution) -> CommandResult | None:
    """Drain the event stream and return the terminal result.

    The application protocol requires consuming the full event stream
    before the terminal result is available. For CLI auth commands we
    don't need the individual events, so we just discard them.
    """
    async for _ in execution.events:
        pass
    return await execution.result()


@app.command("set")
def set_key(
    api_key: Annotated[str, typer.Option("--api-key", help="OpenRouter API key to save")],
) -> None:
    """Save an OpenRouter API key."""
    cmd = AuthSetCommand(api_key=api_key)
    result = asyncio.run(_drain_and_result(dispatch(cmd, config_dir=_config_dir())))

    if isinstance(result, AuthSetResult) and result.saved:
        typer.echo(f"Saved OpenRouter API key to {result.storage_path}")
        raise typer.Exit(code=0)

    # Exit 3 = credential storage error (CLI_SPEC §3)
    typer.echo("Failed to save API key.", err=True)
    raise typer.Exit(code=3)


@app.command()
def status() -> None:
    """Show credential status and verify the key."""
    cmd = AuthStatusCommand()
    result = asyncio.run(_drain_and_result(dispatch(cmd, config_dir=_config_dir())))

    # Guard against unexpected dispatcher failures
    if not isinstance(result, AuthStatusResult):
        typer.echo("Unexpected error checking auth status.", err=True)
        raise typer.Exit(code=3)

    # Always print the full status report before deciding the exit code
    typer.echo(f"Saved key:    {'present' if result.saved_key_present else 'absent'}")
    typer.echo(f"Env key:      {'present' if result.env_key_present else 'absent'}")
    typer.echo(f"Effective:    {result.effective_source}")
    typer.echo(f"Verification: {result.verification}")

    # effective_source is "none" when neither env var nor saved key exists.
    # Exit 3 = missing credentials (CLI_SPEC §3, §5.2)
    if result.effective_source == "none":
        raise typer.Exit(code=3)

    # Exit 4 = key exists but OpenRouter rejected it (CLI_SPEC §3, §5.2)
    if result.verification == "invalid":
        raise typer.Exit(code=4)

    # Exit 0 = key found and either verified or not yet checked
    raise typer.Exit(code=0)


@app.command()
def clear() -> None:
    """Remove the saved API key."""
    cmd = AuthClearCommand()
    result = asyncio.run(_drain_and_result(dispatch(cmd, config_dir=_config_dir())))

    if isinstance(result, AuthClearResult):
        if result.saved_key_removed:
            typer.echo("Removed saved OpenRouter API key.")
        else:
            # No file to delete — still a success per CLI_SPEC §5.3
            typer.echo("No saved key to remove.")
        raise typer.Exit(code=0)

    # Exit 3 = credential storage error (CLI_SPEC §3)
    typer.echo("Failed to clear API key.", err=True)
    raise typer.Exit(code=3)
