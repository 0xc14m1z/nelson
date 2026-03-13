"""Nelson CLI application root."""

import typer

from nelson.cli.auth import app as auth_app
from nelson.cli.run import run

app = typer.Typer(help="Nelson — multi-LLM consensus agent.")
app.add_typer(auth_app, name="auth")
app.command()(run)
