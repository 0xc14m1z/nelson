"""Auth command group stubs."""

from typing import Annotated

import typer

app = typer.Typer(help="Manage OpenRouter API key.")


@app.command("set")
def set_key(
    api_key: Annotated[str, typer.Option("--api-key", help="OpenRouter API key to save")],
) -> None:
    """Save an OpenRouter API key."""
    raise typer.Exit(code=0)


@app.command()
def status() -> None:
    """Show credential status and verify the key."""
    raise typer.Exit(code=0)


@app.command()
def clear() -> None:
    """Remove the saved API key."""
    raise typer.Exit(code=0)
