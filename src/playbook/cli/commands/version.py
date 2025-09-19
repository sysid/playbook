# src/playbook/cli/commands/version.py
"""Version command implementation."""

import typer


def print_version() -> None:
    """Show version"""
    typer.secho("0.6.0", fg=typer.colors.GREEN)
