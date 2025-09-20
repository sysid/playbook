# src/playbook/cli/main.py
"""Main CLI application."""

import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

from .commands.config import config_cmd
from .commands.create import create
from .commands.info import info
from .commands.run import run, resume
from .commands.show import show
from .commands.validate import validate
from .commands.version import print_version
from .commands.view_dag import view_dag

# Create Typer app
app = typer.Typer(
    name="playbook",
    help="Playbook - A workflow engine for operations",
    add_completion=True,
)

# Rich console for pretty output
console = Console()

# Register commands
app.command("config", help="Manage configuration")(config_cmd)
app.command()(create)
app.command()(validate)
app.command()(view_dag)
app.command()(run)
app.command()(resume)
app.command()(info)
app.command()(show)
app.command("version", help="Show version", hidden=True)(print_version)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "-v", "--verbose", help="verbosity"),
    version: bool = typer.Option(False, "-V", "--version", help="show version"),
):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    for logger_name in ("botocore", "boto3", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.INFO)

    if ctx.invoked_subcommand is None and version:
        ctx.invoke(print_version)
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
