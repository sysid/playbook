"""Migrate a schema-v1 runbook to schema v2."""

from pathlib import Path

import typer

from ...infrastructure.migration import LegacyRunbookMigrator
from ..common import console, handle_error_and_exit


def migrate(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Legacy runbook file"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path"),
) -> None:
    """Convert a legacy dependency-based runbook to ordered steps."""
    target = output or file.with_name(f"{file.stem}.v2.toml")
    try:
        LegacyRunbookMigrator().migrate_to(file, target)
        console.print(f"Migrated {file} to {target}")
    except Exception as error:
        handle_error_and_exit(
            error,
            "Runbook migration",
            ctx.params.get("verbose", False),
        )
