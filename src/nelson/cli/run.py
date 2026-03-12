"""Run command stub."""

from pathlib import Path
from typing import Annotated

import typer


def run(
    participant: Annotated[
        list[str],
        typer.Option("--participant", help="Model ID for a participant (at least 2 required)"),
    ],
    moderator: Annotated[str, typer.Option("--moderator", help="Model ID for the moderator")],
    prompt: Annotated[str | None, typer.Option("--prompt", help="Inline prompt text")] = None,
    prompt_file: Annotated[
        Path | None, typer.Option("--prompt-file", help="Path to a prompt file")
    ] = None,
    stdin: Annotated[bool, typer.Option("--stdin", help="Read prompt from stdin")] = False,
    max_rounds: Annotated[int, typer.Option("--max-rounds", help="Maximum consensus rounds")] = 10,
    openrouter_api_key: Annotated[
        str | None, typer.Option("--openrouter-api-key", help="Override OpenRouter API key")
    ] = None,
    release_gate: Annotated[
        str, typer.Option("--release-gate", help="Release gate mode: off, auto, on")
    ] = "auto",
    json: Annotated[bool, typer.Option("--json", help="Output single JSON result")] = False,
    jsonl: Annotated[bool, typer.Option("--jsonl", help="Output JSON Lines event stream")] = False,
) -> None:
    """Run a multi-LLM consensus session."""
    raise typer.Exit(code=0)
