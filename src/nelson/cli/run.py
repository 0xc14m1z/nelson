"""CLI ``run`` command with full argument validation (CLI_SPEC §6.4)."""

from pathlib import Path
from typing import Annotated

import typer

from nelson.cli.exit_codes import ExitCode
from nelson.protocols.enums import ReleaseGateMode


def _fail(message: str) -> None:
    """Print a validation error to stderr and exit with INVALID_USAGE."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=ExitCode.INVALID_USAGE)


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
        ReleaseGateMode,
        typer.Option("--release-gate", help="Release gate mode: off, auto, on"),
    ] = ReleaseGateMode.AUTO,
    json: Annotated[bool, typer.Option("--json", help="Output single JSON result")] = False,
    jsonl: Annotated[bool, typer.Option("--jsonl", help="Output JSON Lines event stream")] = False,
) -> None:
    """Run a multi-LLM consensus session."""
    # ── Validation (CLI_SPEC §6.4) ──────────────────────────────────────
    if len(participant) < 2:
        _fail("At least two --participant flags are required.")

    # Count how many prompt sources were provided
    prompt_sources = sum([prompt is not None, prompt_file is not None, stdin])
    if prompt_sources == 0:
        _fail("A prompt source is required (--prompt, --prompt-file, or --stdin).")
    if prompt_sources > 1:
        _fail("Only one prompt source is allowed (--prompt, --prompt-file, or --stdin).")

    if json and jsonl:
        _fail("--json and --jsonl are mutually exclusive.")

    if len(set(participant)) != len(participant):
        _fail("Duplicate participant model IDs are not allowed.")

    if max_rounds < 1:
        _fail("--max-rounds must be a positive integer.")

    # Validate prompt file exists if provided
    if prompt_file is not None and not prompt_file.is_file():
        _fail(f"Prompt file not found: {prompt_file}")

    # ── Stub: validation passed, actual execution is Phase 6+ ──────────
    raise typer.Exit(code=ExitCode.SUCCESS)
