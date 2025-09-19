# src/playbook/cli/commands/show.py
"""Show command implementation."""

from typing import Optional

import typer
from rich.table import Table

from ..common import console, get_engine, handle_error_and_exit
from ...domain.models import NodeStatus, RunStatus
from ...domain.exceptions import DatabaseError


def show(
    ctx: typer.Context,
    workflow: str = typer.Argument(..., help="Workflow name"),
    run_id: Optional[int] = typer.Option(None, "--run-id", help="Run ID to show"),
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
):
    """Show run details"""
    try:
        engine = get_engine(state_path)

        # Get run repository
        run_repo = engine.run_repo
        node_repo = engine.node_repo

        if run_id is None:
            # List all runs for workflow
            try:
                runs = run_repo.list_runs(workflow)
            except Exception as e:
                raise DatabaseError(
                    f"Failed to retrieve runs for workflow '{workflow}': {str(e)}",
                    context={"workflow": workflow},
                    suggestion="Check database connectivity and ensure the workflow exists"
                )

            if not runs:
                console.print(f"No runs found for workflow: {workflow}")
                return

            # Create table
            table = Table(
                "Run ID",
                "Start Time",
                "Status",
                "Nodes OK",
                "Nodes NOK",
                "Nodes Skipped",
            )

            for run in runs:
                status_color = "green" if run.status == RunStatus.OK else "red"
                table.add_row(
                    str(run.run_id),
                    run.start_time.isoformat() if run.start_time else "",
                    f"[{status_color}]{run.status.value}[/{status_color}]",
                    str(run.nodes_ok),
                    str(run.nodes_nok),
                    str(run.nodes_skipped),
                )

            console.print(table)

        else:
            # Show specific run
            try:
                run = run_repo.get_run(workflow, run_id)
            except Exception as e:
                raise DatabaseError(
                    f"Failed to retrieve run {run_id} for workflow '{workflow}': {str(e)}",
                    context={"workflow": workflow, "run_id": run_id},
                    suggestion="Check that the run ID exists for this workflow"
                )

            console.print(f"[bold]Run: {workflow} #{run_id}[/bold]")
            console.print(
                f"Start time: {run.start_time.isoformat() if run.start_time else 'N/A'}"
            )
            console.print(
                f"End time: {run.end_time.isoformat() if run.end_time else 'N/A'}"
            )

            status_color = "green" if run.status == RunStatus.OK else "red"
            console.print(
                f"Status: [{status_color}]{run.status.value}[/{status_color}]"
            )

            console.print(f"Nodes OK: {run.nodes_ok}")
            console.print(f"Nodes NOK: {run.nodes_nok}")
            console.print(f"Nodes Skipped: {run.nodes_skipped}")

            # Get node executions
            executions = node_repo.get_executions(workflow, run_id)

            if executions:
                console.print("\n[bold]Node Executions:[/bold]")

                table = Table("Node ID", "Status", "Duration", "Start Time")

                for execution in executions:
                    status_color = (
                        "green"
                        if execution.status == NodeStatus.OK
                        else (
                            "yellow"
                            if execution.status == NodeStatus.SKIPPED
                            else "red"
                        )
                    )

                    duration = (
                        f"{execution.duration_ms / 1000:.2f}s"
                        if execution.duration_ms
                        else "N/A"
                    )

                    table.add_row(
                        execution.node_id,
                        f"[{status_color}]{execution.status.value}[/{status_color}]",
                        duration,
                        execution.start_time.isoformat()
                        if execution.start_time
                        else "N/A",
                    )

                console.print(table)

    except Exception as e:
        handle_error_and_exit(e, "Show run details", ctx.params.get('verbose', False))
