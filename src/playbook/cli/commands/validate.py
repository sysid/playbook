"""Validate a schema-v2 runbook."""

from collections import Counter
from pathlib import Path

import typer

from ...domain.exceptions import ParseError
from ..common import (
    console,
    get_parser,
    get_variable_manager,
    handle_error_and_exit,
)


def validate(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    var: list[str] | None = typer.Option(
        None,
        "--var",
        help="Set variable as KEY=VALUE",
    ),
    vars_file: str | None = typer.Option(None, "--vars-file"),
    vars_env: str | None = typer.Option("PLAYBOOK_VAR_", "--vars-env"),
) -> None:
    """Parse and validate a runbook without executing it."""
    try:
        manager = get_variable_manager(interactive=False)
        variables = manager.merge_variables(
            cli_vars=manager.parse_cli_variables(var or []),
            file_vars=(
                manager.load_variables_from_file(vars_file) if vars_file else {}
            ),
            env_vars=manager.load_variables_from_env(vars_env) if vars_env else {},
        )
        runbook = get_parser(interactive=False).parse(file, variables=variables)
        counts = Counter(step.type.value for step in runbook.steps)
        console.print("Runbook is valid")
        console.print(f"Title: {runbook.title}")
        console.print(f"ID: {runbook.id}")
        console.print(f"Steps: {len(runbook.steps)}")
        for step_type in ("manual", "command", "function"):
            console.print(f"{step_type.title()}: {counts[step_type]}")
    except FileNotFoundError:
        handle_error_and_exit(
            ParseError(
                f"Runbook file not found: {file}",
                suggestion="Check the file path",
            ),
            "Runbook validation",
            ctx.params.get("verbose", False),
        )
    except Exception as error:
        handle_error_and_exit(
            error,
            "Runbook validation",
            ctx.params.get("verbose", False),
        )
