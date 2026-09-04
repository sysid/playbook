"""Run and resume ordered playbooks."""

from pathlib import Path
from typing import Any

import typer

from ...domain.models import RunInfo, RunStatus
from ...infrastructure.locking import WorkflowLock
from ..common import (
    console,
    get_engine,
    get_parser,
    get_variable_manager,
    handle_error_and_exit,
)
from ..interaction.handlers import ConsoleNodeIOHandler


def run(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    state_path: str | None = typer.Option(
        None,
        "--state-path",
        help="State database path",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
        min=1,
        help="Maximum executions of a command or function step",
    ),
    var: list[str] | None = typer.Option(
        None,
        "--var",
        help="Set variable as KEY=VALUE",
    ),
    vars_file: str | None = typer.Option(None, "--vars-file"),
    vars_env: str | None = typer.Option("PLAYBOOK_VAR_", "--vars-env"),
    no_interactive_vars: bool = typer.Option(False, "--no-interactive-vars"),
) -> None:
    """Start a guided workflow run."""
    try:
        runbook = _parse_runbook(
            file,
            var,
            vars_file,
            vars_env,
            not no_interactive_vars,
        )
        engine = get_engine(
            state_path,
            ConsoleNodeIOHandler(console),
            max_attempts,
        )
        with WorkflowLock(_lock_path(state_path, runbook.id)):
            result = engine.run(runbook)
        _show_result(result)
    except KeyboardInterrupt:
        console.print("Workflow interrupted; the run was marked aborted.")
        raise typer.Exit(code=130) from None
    except Exception as error:
        handle_error_and_exit(
            error,
            "Runbook execution",
            ctx.params.get("verbose", False),
        )


def resume(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    run_id: int | None = typer.Argument(
        None, help="Run ID; defaults to latest aborted"
    ),
    state_path: str | None = typer.Option(
        None,
        "--state-path",
        help="State database path",
    ),
    max_attempts: int = typer.Option(
        3,
        "--max-attempts",
        min=1,
        help="Maximum executions of a command or function step",
    ),
    var: list[str] | None = typer.Option(None, "--var"),
    vars_file: str | None = typer.Option(None, "--vars-file"),
    vars_env: str | None = typer.Option("PLAYBOOK_VAR_", "--vars-env"),
    no_interactive_vars: bool = typer.Option(False, "--no-interactive-vars"),
) -> None:
    """Continue the first incomplete step of an aborted run."""
    try:
        runbook = _parse_runbook(
            file,
            var,
            vars_file,
            vars_env,
            not no_interactive_vars,
        )
        engine = get_engine(
            state_path,
            ConsoleNodeIOHandler(console),
            max_attempts,
        )
        selected_run_id = run_id or _latest_aborted_run_id(
            engine.run_repo.list_runs(runbook.id)
        )
        if selected_run_id is None:
            raise ValueError(f"No aborted runs found for '{runbook.id}'")
        with WorkflowLock(_lock_path(state_path, runbook.id)):
            result = engine.resume(runbook, selected_run_id)
        _show_result(result)
    except KeyboardInterrupt:
        console.print("Workflow interrupted; the run was marked aborted.")
        raise typer.Exit(code=130) from None
    except Exception as error:
        handle_error_and_exit(
            error,
            "Runbook resume",
            ctx.params.get("verbose", False),
        )


def _parse_runbook(
    file: Path,
    var: list[str] | None,
    vars_file: str | None,
    vars_env: str | None,
    interactive: bool,
):
    variables = _collect_variables(var, vars_file, vars_env, interactive)
    return get_parser(interactive=interactive).parse(file, variables=variables)


def _collect_variables(
    var: list[str] | None,
    vars_file: str | None,
    vars_env: str | None,
    interactive: bool,
) -> dict[str, Any]:
    manager = get_variable_manager(interactive=interactive)
    return manager.merge_variables(
        cli_vars=manager.parse_cli_variables(var or []),
        file_vars=(manager.load_variables_from_file(vars_file) if vars_file else {}),
        env_vars=(manager.load_variables_from_env(vars_env) if vars_env else {}),
    )


def _latest_aborted_run_id(runs: list[RunInfo]) -> int | None:
    aborted = [run.run_id for run in runs if run.status == RunStatus.ABORTED]
    return max(aborted, default=None)


def _lock_path(state_path: str | None, workflow_id: str) -> Path:
    database_path = Path(state_path or "~/.config/playbook/run.db").expanduser()
    return database_path.with_name(f"{database_path.name}.{workflow_id}.lock")


def _show_result(run_info: RunInfo) -> None:
    console.print(
        f"Run {run_info.run_id} finished with status: {run_info.status.value}"
    )
