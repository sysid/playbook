# src/playbook/cli/commands/version.py
"""Version command implementation."""

import typer
from importlib import metadata


def print_version() -> None:
    """Show version"""
    try:
        version = metadata.version("playbook")
    except metadata.PackageNotFoundError:
        version = "unknown"
    typer.secho(version, fg=typer.colors.GREEN)
