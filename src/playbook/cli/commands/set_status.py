# src/playbook/cli/commands/set_status.py
"""Set status command implementation."""

from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm

from ..common import console, get_engine, handle_error_and_exit
from ...domain.models import RunStatus
from ...domain.exceptions import DatabaseError, ParseError
from ...infrastructure.parser import RunbookParser


def set_status(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    run_id: int = typer.Argument(..., help="Run ID to update"),
    new_status: str = typer.Argument(
        ..., help="New status (RUNNING, OK, NOK, ABORTED)"
    ),
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation prompts"
    ),
) -> None:
    """Manually set workflow run status

    This command allows you to manually change the status of a workflow run.
    Common use cases:
    - Fix orphaned RUNNING workflows after system crash
    - Manually mark workflows as completed or failed
    - Reset workflow state for testing

    WARNING: This command directly modifies workflow state. Use with caution.
    """
    try:
        # Parse runbook to get workflow name
        parser = RunbookParser()
        try:
            runbook = parser.parse(str(file))
        except FileNotFoundError:
            raise ParseError(
                f"Runbook file not found: {file}",
                suggestion="Check the file path and ensure the file exists",
            )
        except Exception as e:
            raise ParseError(
                f"Failed to parse runbook: {str(e)}",
                context={"file": str(file)},
                suggestion="Check the TOML syntax and ensure all required fields are present",
            )

        workflow_name = runbook.title

        # Validate new status
        try:
            new_status_enum = RunStatus(new_status.lower())
        except ValueError:
            valid_statuses = ", ".join([s.value.upper() for s in RunStatus])
            console.print(
                f"[bold red]Invalid status: {new_status}[/bold red]\n"
                f"Valid statuses: {valid_statuses}"
            )
            raise typer.Exit(code=1)

        # Get engine and current run info
        engine = get_engine(state_path)

        try:
            run_info = engine.run_repo.get_run(workflow_name, run_id)
        except Exception as e:
            raise DatabaseError(
                f"Failed to retrieve run {run_id} for workflow '{workflow_name}': {str(e)}",
                context={"workflow": workflow_name, "run_id": run_id},
                suggestion="Check that the run ID exists for this workflow",
            )

        current_status = run_info.status

        # Display current state
        console.print(f"\n[bold]Workflow:[/bold] {workflow_name}")
        console.print(f"[bold]Run ID:[/bold] {run_id}")

        current_color = _get_status_color(current_status)
        new_color = _get_status_color(new_status_enum)

        console.print(
            f"[bold]Current status:[/bold] [{current_color}]{current_status.value.upper()}[/{current_color}]"
        )
        console.print(
            f"[bold]New status:[/bold] [{new_color}]{new_status_enum.value.upper()}[/{new_color}]"
        )

        # Safety checks
        if current_status == new_status_enum:
            console.print(
                f"\n[yellow]Status is already {new_status_enum.value.upper()}. No change needed.[/yellow]"
            )
            return

        warnings = []

        # Warn if changing from terminal state to non-terminal
        terminal_states = {RunStatus.OK, RunStatus.NOK}
        non_terminal_states = {RunStatus.RUNNING, RunStatus.ABORTED}

        if current_status in terminal_states and new_status_enum in non_terminal_states:
            warnings.append(
                f"⚠️  Changing from terminal state {current_status.value.upper()} to "
                f"non-terminal state {new_status_enum.value.upper()}. This is unusual."
            )

        # Warn if setting to RUNNING
        if new_status_enum == RunStatus.RUNNING:
            warnings.append(
                "⚠️  Setting status to RUNNING may interfere with workflow execution. "
                "Ensure no other process is running this workflow."
            )

        # Display warnings
        if warnings:
            console.print()
            for warning in warnings:
                console.print(f"[bold yellow]{warning}[/bold yellow]")

        # Confirmation prompt
        if not force:
            console.print()
            confirmed = Confirm.ask(
                f"Set status of {workflow_name}#{run_id} from "
                f"{current_status.value.upper()} to {new_status_enum.value.upper()}?",
                default=False,
            )

            if not confirmed:
                console.print("[yellow]Operation cancelled.[/yellow]")
                raise typer.Exit(code=0)

        # Update status
        run_info.status = new_status_enum
        engine.run_repo.update_run(run_info)

        console.print(
            f"\n[bold green]✓[/bold green] Status updated to "
            f"[{new_color}]{new_status_enum.value.upper()}[/{new_color}]"
        )

        # Provide helpful next steps
        if new_status_enum == RunStatus.ABORTED:
            console.print(
                f"\n[dim]You can now resume this workflow with:[/dim]\n"
                f"  playbook resume {file} {run_id}"
            )

    except Exception as e:
        handle_error_and_exit(e, "Set status", ctx.params.get("verbose", False))


def _get_status_color(status: RunStatus) -> str:
    """Get Rich color for status display."""
    color_map = {
        RunStatus.OK: "green",
        RunStatus.NOK: "red",
        RunStatus.RUNNING: "blue",
        RunStatus.ABORTED: "yellow",
    }
    return color_map.get(status, "white")
