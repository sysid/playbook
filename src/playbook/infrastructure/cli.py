# src/playbook/infrastructure/cli.py
import datetime
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.prompt import Confirm, Prompt
from rich.table import Table

from playbook.infrastructure.statistics import SQLiteStatisticsRepository
from playbook.service.statistics import StatisticsService
from ..config import load_config
from ..domain.models import NodeStatus, NodeType, RunStatus
from ..domain.ports import Clock, NodeIOHandler
from ..infrastructure.functions import PythonFunctionLoader
from ..infrastructure.parser import RunbookParser
from ..infrastructure.persistence import SQLiteRunRepository, SQLiteNodeExecutionRepository
from ..infrastructure.process import ShellProcessRunner
from ..infrastructure.visualization import GraphvizVisualizer
from ..service.engine import RunbookEngine

logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    name="playbook",
    help="Playbook - A workflow engine for operations",
    add_completion=False
)

# Rich console for pretty output
console = Console()


class SystemClock(Clock):
    """System clock implementation"""

    def now(self) -> datetime.datetime:
        """Get current time"""
        return datetime.datetime.now(datetime.timezone.utc)


class ConsoleNodeIOHandler(NodeIOHandler):
    """Console implementation of NodeIOHandler"""

    def __init__(self, console: Console, progress: Optional[Progress] = None):
        self.console = console
        self.progress = progress

    def handle_manual_prompt(self, node_id: str, node_name: Optional[str], prompt: str) -> bool:
        """Display prompt and get user decision"""
        display_name = node_name or node_id

        # Pause progress bar if it exists
        if self.progress:
            self.progress.stop()

        # Show prompt and get decision
        self.console.print(f"[bold blue]Manual Step ({display_name}):[/bold blue]")
        self.console.print(prompt)

        from rich.prompt import Confirm
        decision = Confirm.ask("Approve?")

        self.console.print("")
        # Resume progress bar if it exists
        if self.progress:
            self.progress.start()

        return decision

    def handle_command_output(self, node_id: str, node_name: Optional[str], stdout: str, stderr: str) -> None:
        """Display command output"""
        display_name = node_name or node_id

        # Only process if there's output to show
        if not (stdout.strip() or stderr.strip()):
            return

        # Pause progress bar if it exists
        if self.progress:
            self.progress.stop()

        # Show output
        if stdout.strip():
            self.console.print(f"[bold green]Command Output ({display_name}):[/bold green]")
            self.console.print(stdout)

        if stderr.strip():
            self.console.print(f"[bold yellow]Command Error ({display_name}):[/bold yellow]")
            self.console.print(stderr)

        self.console.print("")
        # Resume progress bar if it exists
        if self.progress:
            self.progress.start()

    def handle_function_output(self, node_id: str, node_name: Optional[str], result: str) -> None:
        """Display function output"""
        display_name = node_name or node_id

        # Only process if there's output to show
        if not result.strip():
            return

        # Pause progress bar if it exists
        if self.progress:
            self.progress.stop()

        # Show output
        self.console.print(f"[bold blue]Function Output ({display_name}):[/bold blue]")
        self.console.print(result)

        self.console.print("")
        # Resume progress bar if it exists
        if self.progress:
            self.progress.start()


def get_engine(state_path: Optional[str] = None, io_handler: Optional[NodeIOHandler] = None) -> RunbookEngine:
    """Create and configure the runbook engine"""
    # Load configuration
    config = load_config()

    # Override state path if provided
    if state_path:
        config["state_path"] = state_path

    logger.debug(f"Using state path: {config['state_path']}")

    # Create dependencies
    clock = SystemClock()
    process_runner = ShellProcessRunner()
    function_loader = PythonFunctionLoader()
    run_repo = SQLiteRunRepository(config["state_path"])
    node_repo = SQLiteNodeExecutionRepository(config["state_path"])

    # Create engine
    return RunbookEngine(
        clock=clock,
        process_runner=process_runner,
        function_loader=function_loader,
        run_repo=run_repo,
        node_repo=node_repo,
        io_handler=io_handler
    )


@app.command()
def create(
    title: str = typer.Option(..., "--title", help="Runbook title"),
    author: str = typer.Option(..., "--author", help="Author name"),
    description: str = typer.Option(None, "--description", help="Runbook description"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output file path")
):
    """Create a new empty runbook file"""
    # Set default description if none provided
    if description is None:
        description = f"Runbook for {title}"

    # Set default output path if none provided
    if output is None:
        output = Path(f"{title.lower().replace(' ', '_')}.playbook.toml")

    # Check if file exists
    if output.exists():
        if not Confirm.ask(f"File {output} already exists. Overwrite?"):
            return

    # Create a simple template runbook
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create the template content
    template = f"""[runbook]
title       = "{title}"
description = "{description}"
version     = "0.1.0"
author      = "{author}"
created_at  = "{now.isoformat()}"

# Example manual node - uncomment to use
# [approve]
# type        = "Manual"
# prompt      = "Proceed with deployment?"
# depends_on  = []
# skippable   = false
# critical    = true

# Example command node - uncomment to use
# [build]
# type         = "Command"
# command_name = "echo 'Hello, World!'"
# depends_on   = []
# timeout      = 300
# name         = "Build step"

# Example function node - uncomment to use
# [notify]
# type           = "Function"
# function_name  = "playbook.functions.notify"
# function_params = {{ "message" = "Deployment complete" }}
# depends_on     = []
"""

    # Write the template to file
    output.write_text(template)

    console.print(f"[bold green]Created new runbook at {output}[/bold green]")
    console.print("\nEdit this file to add your nodes and customize the workflow.")
    console.print("Use 'playbook validate' to check your runbook for correctness.")


@app.command()
def validate(
    file: Path = typer.Argument(..., help="Runbook file path"),
    strict: bool = typer.Option(False, "--strict", help="Enable strict validation")
):
    """Validate a runbook file"""
    parser = RunbookParser()
    engine = get_engine()

    try:
        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        runbook = parser.parse(str(file))

        # Validate runbook
        console.print("Validating runbook...")
        errors = engine.validate(runbook)

        if errors:
            console.print("[bold red]Validation errors:[/bold red]")
            for error in errors:
                console.print(f"  • {error}")
            sys.exit(1)
        else:
            console.print("[bold green]Runbook is valid![/bold green]")

            # Print summary
            console.print(f"\n[bold]Runbook: {runbook.title}[/bold]")
            console.print(f"Description: {runbook.description}")
            console.print(f"Version: {runbook.version}")
            console.print(f"Author: {runbook.author}")
            console.print(f"Created: {runbook.created_at.isoformat()}")
            console.print(f"Nodes: {len(runbook.nodes)}")

            # Print node types
            manual_count = sum(1 for n in runbook.nodes.values() if n.type == NodeType.MANUAL)
            function_count = sum(1 for n in runbook.nodes.values() if n.type == NodeType.FUNCTION)
            command_count = sum(1 for n in runbook.nodes.values() if n.type == NodeType.COMMAND)

            console.print(f"  • Manual nodes: {manual_count}")
            console.print(f"  • Function nodes: {function_count}")
            console.print(f"  • Command nodes: {command_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def export_dot(
    file: Path = typer.Argument(..., help="Runbook file path"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output DOT file path")
):
    """Export runbook as DOT file for Graphviz"""
    parser = RunbookParser()
    visualizer = GraphvizVisualizer()

    try:
        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        runbook = parser.parse(str(file))

        # Determine output path
        if not output:
            output = file.with_suffix(".dot")

        # Export to DOT
        console.print(f"Exporting to DOT: {output}")
        visualizer.export_dot(runbook, str(output))

        console.print(f"[bold green]DOT file created: {output}[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def run(
    file: Path = typer.Argument(..., help="Runbook file path"),
    state_path: Optional[str] = typer.Option(None, "--state-path", help="State database path")
):
    """Run a playbook from start to finish"""
    parser = RunbookParser()

    try:
        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        runbook = parser.parse(str(file))

        # Execute nodes
        with Progress() as progress:
            io_handler = ConsoleNodeIOHandler(console, progress)
            engine = get_engine(state_path, io_handler)

            console.print(f"Starting run: {runbook.title}")
            run_info = engine.start_run(runbook)

            console.print(f"Run ID: {run_info.run_id}")

            # Get execution order
            order = engine._get_execution_order(runbook)

            task = progress.add_task("Running...", total=len(order))

            for node_id in order:
                node = runbook.nodes[node_id]

                progress.update(task, description=f"Running {node.name or node_id}")

                # Execute node
                status, execution = engine.execute_node(runbook, node_id, run_info)

                # Handle result
                if status == NodeStatus.OK:
                    progress.update(task, description=f"Completed: {node.name or node_id}")
                elif status == NodeStatus.NOK:
                    progress.update(task, description=f"Failed: {node.name or node_id}")

                    # Display error
                    if execution.exception:
                        console.print(f"[bold red]Error:[/bold red] {execution.exception}")

                    if execution.stderr:
                        console.print(f"[bold red]stderr:[/bold red]\n{execution.stderr}")

                    # If node is critical, abort
                    if node.critical:
                        console.print("[bold red]Critical node failed, aborting[/bold red]")
                        break

                    # Ask user what to do
                    choice = Prompt.ask(
                        "Node failed. What would you like to do?",
                        choices=["r", "s", "a"],
                        default="r"
                    )

                    if choice == "r":
                        # Retry would be implemented here
                        console.print("Retry not implemented in prototype")
                    elif choice == "s":
                        if not node.skippable:
                            console.print("[bold red]Cannot skip non-skippable node[/bold red]")
                            # Retry would be forced here
                        else:
                            console.print("Skipping node")
                            # Skip logic would be implemented here
                    elif choice == "a":
                        console.print("Aborting run")
                        break

                progress.update(task, advance=1)

        # Update run status
        final_status = engine.update_run_status(runbook, run_info)

        if final_status == RunStatus.OK:
            console.print("[bold green]Run completed successfully[/bold green]")
        else:
            console.print("[bold red]Run failed[/bold red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def resume(
    file: Path = typer.Argument(..., help="Runbook file path"),
    run_id: int = typer.Argument(..., help="Run ID to resume"),
    node_id: Optional[str] = typer.Option(None, "--node", help="Node ID to resume from"),
    state_path: Optional[str] = typer.Option(None, "--state-path", help="State database path")
):
    """Resume a previously started run"""
    parser = RunbookParser()

    try:
        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        runbook = parser.parse(str(file))

        # Execute nodes
        with Progress() as progress:
            # Create IO handler
            io_handler = ConsoleNodeIOHandler(console, progress)

            # Get engine with IO handler
            engine = get_engine(state_path, io_handler)

            console.print(f"Resuming run: {runbook.title} (Run ID: {run_id})")
            run_info = engine.resume_run(runbook, run_id)

            # Get execution order
            order = engine._get_execution_order(runbook)

            # Get existing executions to determine what to run
            existing_executions = engine.node_repo.get_executions(runbook.title, run_id)

            # Create a map of node_id to its execution status
            node_status = {}
            for execution in existing_executions:
                if execution.node_id not in node_status or execution.status != NodeStatus.OK:
                    node_status[execution.node_id] = execution.status

            # Determine which nodes to run based on their status and dependencies
            nodes_to_run = []

            # If a start node is specified, find its index in the execution order
            start_idx = 0
            if node_id:
                try:
                    start_idx = order.index(node_id)
                except ValueError:
                    raise ValueError(f"Start node '{node_id}' not found in runbook")

            # Include all nodes from start_idx that haven't successfully completed
            for i in range(start_idx, len(order)):
                current_node_id = order[i]

                # Skip nodes that are already OK or SKIPPED
                if current_node_id in node_status and node_status[current_node_id] in [NodeStatus.OK,
                                                                                       NodeStatus.SKIPPED]:
                    continue

                # Include this node and any dependencies that need to be run
                nodes_to_run.append(current_node_id)

            if not nodes_to_run:
                console.print("[bold yellow]No nodes to resume - all nodes are already completed[/bold yellow]")
                return

            # Run the nodes that need running
            task = progress.add_task("Resuming...", total=len(nodes_to_run))

            for idx, current_node_id in enumerate(nodes_to_run):
                node = runbook.nodes[current_node_id]
                node_display_name = node.name or current_node_id

                progress.update(task, description=f"Running {node_display_name}")

                # Determine if we need to create a new execution or update an existing one
                existing_execution = None
                for execution in existing_executions:
                    if execution.node_id == current_node_id:
                        existing_execution = execution
                        break

                # Execute the node
                if existing_execution and existing_execution.status in [NodeStatus.RUNNING, NodeStatus.PENDING]:
                    # Update existing execution to avoid unique constraint error
                    status, execution = engine.execute_node_with_existing_record(
                        runbook, current_node_id, run_info, existing_execution.attempt
                    )
                else:
                    # Create new execution record
                    status, execution = engine.execute_node(
                        runbook, current_node_id, run_info
                    )

                # Handle failure
                if status == NodeStatus.OK:
                    progress.update(task, description=f"Completed: {node.name or node_id}")
                elif status == NodeStatus.NOK:
                    progress.update(task, description=f"Failed: {node_display_name}")

                    # Display error information
                    if execution.exception:
                        console.print(f"[bold red]Error:[/bold red] {execution.exception}")

                    if execution.stderr:
                        console.print(f"[bold red]stderr:[/bold red]\n{execution.stderr}")

                    # Critical failure stops the workflow
                    if node.critical:
                        console.print("[bold red]Critical node failed, aborting[/bold red]")
                        break

                    # Interactive decision
                    choice = Prompt.ask(
                        "Node failed. What would you like to do?",
                        choices=["r", "s", "a"],
                        default="r"
                    )

                    if choice == "r":
                        # Retry would go here in a full implementation
                        console.print("Retry not implemented in prototype")
                    elif choice == "s":
                        if not node.skippable:
                            console.print("[bold red]Cannot skip non-skippable node[/bold red]")
                        else:
                            console.print("Skipping node")
                            execution.status = NodeStatus.SKIPPED
                            engine.node_repo.update_execution(execution)
                    elif choice == "a":
                        console.print("Aborting run")
                        break

                # Update progress
                progress.update(task, advance=1)

                # If we've reached the end, make sure to update run status
                if idx == len(nodes_to_run) - 1:
                    engine.update_run_status(runbook, run_info)

        # Final run status update
        final_status = engine.update_run_status(runbook, run_info)

        if final_status == RunStatus.OK:
            console.print("[bold green]Run completed successfully[/bold green]")
        else:
            console.print("[bold red]Run failed[/bold red]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

@app.command()
def info(
    json_format: bool = typer.Option(False, "--json", help="Output as JSON"),
    show_ddl: bool = typer.Option(False, "--ddl", help="Show database schema as DDL")
):
    """Show database info and workflow statistics"""
    config = load_config()

    try:
        # Create statistics service
        stats_repo = SQLiteStatisticsRepository(config["state_path"])
        stats_service = StatisticsService(stats_repo)

        # Get database info
        db_info = stats_service.get_database_info()

        if not db_info.get("exists", False):
            console.print(f"Database does not exist yet: {db_info.get('path')}")
            return

        # Show database info
        console.print(f"[bold]Database Information:[/bold]")
        console.print(f"Path: {db_info['path']}")
        console.print(f"Size: {db_info['size_kb']:.2f} KB")

        # Show workflow statistics
        workflow_stats = stats_service.get_workflow_statistics()

        if workflow_stats:
            console.print("\n[bold]Workflow Statistics:[/bold]")

            # Create workflow stats table
            table = Table("Workflow", "Total Runs", "OK", "NOK", "Running", "Aborted", "Latest Run")

            for workflow_name, stats in workflow_stats.items():
                status_counts = stats["status_counts"]
                ok_count = status_counts.get("ok", 0)
                nok_count = status_counts.get("nok", 0)
                running_count = status_counts.get("running", 0)
                aborted_count = status_counts.get("aborted", 0)

                table.add_row(
                    workflow_name,
                    str(stats["total_runs"]),
                    str(ok_count),
                    str(nok_count),
                    str(running_count),
                    str(aborted_count),
                    stats["latest_run"] or "N/A"
                )

            console.print(table)

        # Show node statistics
        node_stats = stats_service.get_node_statistics()

        if node_stats:
            console.print("\n[bold]Node Statistics:[/bold]")

            # Create node stats table
            table = Table("Workflow", "Node", "OK", "NOK", "Skipped", "Pending", "Running")

            for key, stats in node_stats.items():
                status_counts = stats["status_counts"]

                table.add_row(
                    stats["workflow_name"],
                    stats["node_id"],
                    str(status_counts.get("ok", 0)),
                    str(status_counts.get("nok", 0)),
                    str(status_counts.get("skipped", 0)),
                    str(status_counts.get("pending", 0)),
                    str(status_counts.get("running", 0))
                )

            console.print(table)

        # Show DDL if requested
        if show_ddl:
            console.print("\n[bold]Database Schema DDL:[/bold]")

            ddl_statements = stats_service.get_schema_ddl()

            for ddl in ddl_statements:
                console.print(f"\n{ddl};")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def show(
    workflow: str = typer.Argument(..., help="Workflow name"),
    run_id: Optional[int] = typer.Option(None, "--run-id", help="Run ID to show"),
    state_path: Optional[str] = typer.Option(None, "--state-path", help="State database path")
):
    """Show run details"""
    engine = get_engine(state_path)

    try:
        # Get run repository
        run_repo = engine.run_repo
        node_repo = engine.node_repo

        if run_id is None:
            # List all runs for workflow
            runs = run_repo.list_runs(workflow)

            if not runs:
                console.print(f"No runs found for workflow: {workflow}")
                return

            # Create table
            table = Table("Run ID", "Start Time", "Status", "Nodes OK", "Nodes NOK", "Nodes Skipped")

            for run in runs:
                status_color = "green" if run.status == RunStatus.OK else "red"
                table.add_row(
                    str(run.run_id),
                    run.start_time.isoformat() if run.start_time else "",
                    f"[{status_color}]{run.status.value}[/{status_color}]",
                    str(run.nodes_ok),
                    str(run.nodes_nok),
                    str(run.nodes_skipped)
                )

            console.print(table)

        else:
            # Show specific run
            run = run_repo.get_run(workflow, run_id)

            console.print(f"[bold]Run: {workflow} #{run_id}[/bold]")
            console.print(f"Start time: {run.start_time.isoformat() if run.start_time else 'N/A'}")
            console.print(f"End time: {run.end_time.isoformat() if run.end_time else 'N/A'}")

            status_color = "green" if run.status == RunStatus.OK else "red"
            console.print(f"Status: [{status_color}]{run.status.value}[/{status_color}]")

            console.print(f"Nodes OK: {run.nodes_ok}")
            console.print(f"Nodes NOK: {run.nodes_nok}")
            console.print(f"Nodes Skipped: {run.nodes_skipped}")

            # Get node executions
            executions = node_repo.get_executions(workflow, run_id)

            if executions:
                console.print("\n[bold]Node Executions:[/bold]")

                table = Table("Node ID", "Status", "Duration", "Start Time")

                for execution in executions:
                    status_color = "green" if execution.status == NodeStatus.OK else (
                        "yellow" if execution.status == NodeStatus.SKIPPED else "red"
                    )

                    duration = f"{execution.duration_ms / 1000:.2f}s" if execution.duration_ms else "N/A"

                    table.add_row(
                        execution.node_id,
                        f"[{status_color}]{execution.status.value}[/{status_color}]",
                        duration,
                        execution.start_time.isoformat() if execution.start_time else "N/A"
                    )

                console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


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
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    for logger_name in ('botocore', 'boto3', 'urllib3'):
        logging.getLogger(logger_name).setLevel(logging.INFO)

    if ctx.invoked_subcommand is None and version:
        ctx.invoke(print_version)
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())


@app.command("version", help="Show version", hidden=True)
def print_version() -> None:
    typer.secho("0.1.0", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
