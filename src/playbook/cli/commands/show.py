"""Inspect persisted workflow runs."""

from pathlib import Path

import typer
from rich.table import Table

from ...infrastructure.persistence import (
    SQLiteNodeExecutionRepository,
    SQLiteRunRepository,
)
from ..common import console, handle_error_and_exit


def show(
    ctx: typer.Context,
    workflow: str = typer.Argument(..., help="Workflow ID"),
    run_id: int | None = typer.Option(None, "--run-id", help="Run ID"),
    state_path: str | None = typer.Option(None, "--state-path"),
) -> None:
    """List workflow history or display one run."""
    database = str(Path(state_path or "~/.config/playbook/run.db").expanduser())
    try:
        runs = SQLiteRunRepository(database)
        if run_id is None:
            _show_runs(workflow, runs.list_runs(workflow))
            return
        run = runs.get_run(workflow, run_id)
        executions = SQLiteNodeExecutionRepository(database).get_executions(
            workflow,
            run_id,
        )
        console.print(f"[bold]{workflow} #{run_id}[/bold] / {run.status.value}")
        console.print(f"Started: {run.start_time.isoformat()}")
        if run.end_time:
            console.print(f"Finished: {run.end_time.isoformat()}")
        table = Table("Step", "Attempt", "Status", "Duration")
        for execution in executions:
            duration = (
                f"{execution.duration_ms / 1000:.2f}s"
                if execution.duration_ms is not None
                else "-"
            )
            table.add_row(
                execution.node_id,
                str(execution.attempt),
                execution.status.value,
                duration,
            )
        console.print(table)
    except Exception as error:
        handle_error_and_exit(
            error,
            "Show workflow history",
            ctx.params.get("verbose", False),
        )


def _show_runs(workflow: str, runs) -> None:
    if not runs:
        console.print(f"No runs found for workflow: {workflow}")
        return
    console.print(f"[bold]{workflow}[/bold]")
    table = Table("Run", "Started", "Status", "OK", "Failed", "Skipped")
    for run in runs:
        table.add_row(
            str(run.run_id),
            run.start_time.isoformat(),
            run.status.value,
            str(run.nodes_ok),
            str(run.nodes_nok),
            str(run.nodes_skipped),
        )
    console.print(table)
