# src/playbook/infrastructure/cli.py
import datetime
import logging
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.prompt import Confirm, Prompt
from rich.table import Table

from playbook.infrastructure.statistics import SQLiteStatisticsRepository
from playbook.service.statistics import StatisticsService
from ..config import load_config
from ..domain.models import (
    NodeStatus,
    NodeType,
    RunStatus,
    Runbook,
    RunInfo,
    TriggerType,
)
from ..domain.ports import Clock, NodeIOHandler
from ..infrastructure.functions import PythonFunctionLoader
from ..infrastructure.parser import RunbookParser
from ..infrastructure.persistence import (
    SQLiteRunRepository,
    SQLiteNodeExecutionRepository,
)
from ..infrastructure.process import ShellProcessRunner
from ..infrastructure.visualization import GraphvizVisualizer
from ..service.engine import RunbookEngine

logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    name="playbook",
    help="Playbook - A workflow engine for operations",
    add_completion=False,
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
        self.displayed_descriptions = set()  # Track which nodes have shown descriptions
        self.current_node_id = None  # Track which node is currently executing

    def set_current_node(self, node_id: str):
        """Set the current node being processed"""
        self.current_node_id = node_id

    def handle_manual_prompt(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        prompt: str,
    ) -> bool:
        """Display prompt and get user decision"""
        display_name = node_name or node_id

        self.console.print(f"[bold blue]Manual Step ({display_name}):[/bold blue]")

        # Print description if available and not already shown
        node_key = f"{node_id}-description"
        if description and node_key not in self.displayed_descriptions:
            self.console.print(f"\n[italic]{description}[/italic]\n")
            self.displayed_descriptions.add(node_key)

        self.console.print(prompt)

        from rich.prompt import Confirm

        decision = Confirm.ask("Approve?")

        self.console.print("")
        return decision

    def handle_command_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        stdout: str,
        stderr: str,
    ) -> None:
        """Display command output"""
        display_name = node_name or node_id
        node_key = f"{node_id}-description"

        # Only process if there's output to show
        if not (stdout.strip() or stderr.strip()):
            return

        # Print description if available and not already shown
        if description and node_key not in self.displayed_descriptions:
            self.console.print(f"\n[italic]{description}[/italic]\n")
            self.displayed_descriptions.add(node_key)

        if stdout.strip():
            self.console.print(
                f"[bold green]Command Output ({display_name}):[/bold green]"
            )
            self.console.print(stdout)

        if stderr.strip():
            self.console.print(
                f"[bold yellow]Command Error ({display_name}):[/bold yellow]"
            )
            self.console.print(stderr)

        self.console.print("")

    def handle_function_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        result: str,
    ) -> None:
        """Display function output"""
        display_name = node_name or node_id
        node_key = f"{node_id}-description"

        # Only process if there's output to show
        if not result.strip():
            return

        # Print description if available and not already shown
        if description and node_key not in self.displayed_descriptions:
            self.console.print(f"\n[italic]{description}[/italic]\n")
            self.displayed_descriptions.add(node_key)

        # Show output
        self.console.print(f"[bold blue]Function Output ({display_name}):[/bold blue]")
        self.console.print(result)

        self.console.print("")


def get_engine(
    state_path: Optional[str] = None, io_handler: Optional[NodeIOHandler] = None
) -> RunbookEngine:
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
        io_handler=io_handler,
    )


@app.command()
def create(
    title: str = typer.Option(..., "--title", help="Runbook title"),
    author: str = typer.Option(..., "--author", help="Author name"),
    description: str = typer.Option(None, "--description", help="Runbook description"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output file path"),
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
# description   = \"\"\"This step requires manual approval before proceeding.
# Please review the changes and confirm.\"\"\"
# depends_on  = []
# skippable   = false
# critical    = true

# Example command node - uncomment to use
# [build]
# type         = "Command"
# command_name = "echo 'Hello, World!'"
# description  = "Builds the project artifacts"
# depends_on   = []
# timeout      = 300
# name         = "Build step"

# Example function node - uncomment to use
# [notify]
# type           = "Function"
# function_name  = "playbook.functions.notify"
# function_params = {{ "message" = "Deployment complete" }}
# description    = "Sends deployment completion notification"
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
    strict: bool = typer.Option(False, "--strict", help="Enable strict validation"),
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
            manual_count = sum(
                1 for n in runbook.nodes.values() if n.type == NodeType.MANUAL
            )
            function_count = sum(
                1 for n in runbook.nodes.values() if n.type == NodeType.FUNCTION
            )
            command_count = sum(
                1 for n in runbook.nodes.values() if n.type == NodeType.COMMAND
            )

            console.print(f"  • Manual nodes: {manual_count}")
            console.print(f"  • Function nodes: {function_count}")
            console.print(f"  • Command nodes: {command_count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def export_dot(
    file: Path = typer.Argument(..., help="Runbook file path"),
    output: Optional[Path] = typer.Option(
        None, "--output", help="Output DOT file path"
    ),
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
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
):
    """Run a playbook from start to finish"""
    parser = RunbookParser()
    _execute_workflow(parser, file, state_path)


@app.command()
def resume(
    file: Path = typer.Argument(..., help="Runbook file path"),
    run_id: int = typer.Argument(..., help="Run ID to resume"),
    node_id: Optional[str] = typer.Option(
        None, "--node", help="Node ID to resume from"
    ),
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
):
    """Resume a previously started run"""
    parser = RunbookParser()
    _execute_workflow(parser, file, state_path, run_id, node_id)


def _execute_workflow(
    parser: RunbookParser,
    file: Path,
    state_path: Optional[str] = None,
    run_id: Optional[int] = None,
    start_node_id: Optional[str] = None,
) -> None:
    """
    Shared workflow execution logic for both run and resume commands
    """
    try:
        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        runbook = parser.parse(str(file))

        # Create progress display and IO handler
        progress = Progress()
        io_handler = ConsoleNodeIOHandler(console, progress)
        engine = get_engine(state_path, io_handler)

        # Initialize run info based on whether we're resuming or starting fresh
        if run_id is not None:
            console.print(f"Resuming run: {runbook.title} (Run ID: {run_id})")
            run_info = engine.resume_run(runbook, run_id, start_node_id)
        else:
            console.print(f"Starting run: {runbook.title}")
            run_info = engine.start_run(runbook)
            console.print(f"Run ID: {run_info.run_id}")

        # Get execution order
        order = engine._get_execution_order(runbook)

        # Determine which nodes to run
        nodes_to_run = _determine_nodes_to_run(
            engine, runbook, run_info, order, start_node_id
        )

        if not nodes_to_run:
            console.print(
                "[bold yellow]No nodes to execute - all nodes are already completed[/bold yellow]"
            )
            return

        # Execute the workflow
        _execute_nodes(engine, runbook, run_info, nodes_to_run, progress, io_handler)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def _determine_nodes_to_run(
    engine: RunbookEngine,
    runbook: Runbook,
    run_info: RunInfo,
    order: List[str],
    start_node_id: Optional[str] = None,
) -> List[str]:
    """
    Determine which nodes need to be executed based on run state
    """
    # For a new run, execute all nodes
    if run_info.trigger == TriggerType.RUN:
        return order

    # For resume, get existing executions to determine what to run
    existing_executions = engine.node_repo.get_executions(
        runbook.title, run_info.run_id
    )

    # Create a map of node_id to its latest execution
    node_executions = {}
    for execution in existing_executions:
        node_executions[execution.node_id] = execution

    # Determine which nodes to run
    start_idx = 0
    if start_node_id:
        try:
            start_idx = order.index(start_node_id)
        except ValueError:
            raise ValueError(f"Start node '{start_node_id}' not found in runbook")

    # Include all nodes from start_idx that haven't successfully completed
    nodes_to_run = []
    for i in range(start_idx, len(order)):
        current_node_id = order[i]
        if current_node_id not in node_executions or node_executions[
            current_node_id
        ].status not in [NodeStatus.OK, NodeStatus.SKIPPED]:
            nodes_to_run.append(current_node_id)

    return nodes_to_run


def _execute_nodes(
    engine: RunbookEngine,
    runbook: Runbook,
    run_info: RunInfo,
    nodes_to_run: List[str],
    progress: Progress,
    io_handler: ConsoleNodeIOHandler,
) -> None:
    """
    Execute the given nodes in the runbook
    """
    # Get all existing executions at the beginning
    existing_executions = engine.node_repo.get_executions(
        runbook.title, run_info.run_id
    )
    existing_executions_map = {ex.node_id: ex for ex in existing_executions}

    # Start the progress display with a single task
    with progress:
        task = progress.add_task("Executing workflow...", total=len(nodes_to_run) + 1)

        for i, current_node_id in enumerate(nodes_to_run):
            node = runbook.nodes[current_node_id]
            node_display_name = node.name or current_node_id

            # Set the current node in the IO handler
            io_handler.set_current_node(current_node_id)

            # Update progress bar with current node
            progress.start()
            progress.update(task, description=f"Running {node_display_name}")
            # Hide the progress bar during execution to prevent duplicate display
            progress.stop()

            # Check if this node has an existing execution record
            existing_execution = existing_executions_map.get(current_node_id)

            # Execute node based on whether it has an existing execution
            if existing_execution and existing_execution.status != NodeStatus.OK:
                # Resume with existing record
                status, execution = engine.resume_node_execution(
                    runbook, current_node_id, run_info, existing_execution
                )
            else:
                # Create new execution record (for fresh nodes)
                status, execution = engine.execute_node(
                    runbook, current_node_id, run_info
                )

            # Update progress based on result
            if status == NodeStatus.OK:
                progress.update(
                    task, description=f"Completed: {node_display_name}", advance=1
                )
            elif status == NodeStatus.NOK:
                progress.update(
                    task, description=f"Failed: {node_display_name}", advance=1
                )

                # Handle node failure
                if execution.exception:
                    console.print(f"[bold red]Error:[/bold red] {execution.exception}")

                if execution.stderr:
                    console.print(f"[bold red]stderr:[/bold red]\n{execution.stderr}")

                # If node is critical, abort
                if node.critical:
                    console.print("[bold red]Critical node failed, aborting[/bold red]")
                    break

                # Ask user what to do
                progress.stop()  # Hide progress bar for user interaction
                choice = Prompt.ask(
                    "Node failed. What would you like to do?",
                    choices=["r", "s", "a"],
                    default="r",
                )

                if choice == "r":
                    console.print("Retry not implemented in prototype")
                elif choice == "s":
                    if not node.skippable:
                        console.print(
                            "[bold red]Cannot skip non-skippable node[/bold red]"
                        )
                    else:
                        console.print("Skipping node")
                        execution.status = NodeStatus.SKIPPED
                        engine.node_repo.update_execution(execution)
                elif choice == "a":
                    console.print("Aborting run")
                    run_info.status = RunStatus.ABORTED
                    engine.run_repo.update_run(run_info)
                    break

            engine.update_run_status(runbook, run_info)

        # Update run status
        final_status = engine.update_run_status(runbook, run_info)

        # Show final status
        if final_status == RunStatus.OK:
            progress.start()  # Avoid showing progress on failure again
            console.print("\n[bold green]Run completed successfully[/bold green]")
            progress.update(task, description="Success!", advance=1)
        else:
            console.print("\n[bold red]Run failed[/bold red]")


@app.command()
def info(
    json_format: bool = typer.Option(False, "--json", help="Output as JSON"),
    show_ddl: bool = typer.Option(False, "--ddl", help="Show database schema as DDL"),
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
        console.print("[bold]Database Information:[/bold]")
        console.print(f"Path: {db_info['path']}")
        console.print(f"Size: {db_info['size_kb']:.2f} KB")

        # Show workflow statistics
        workflow_stats = stats_service.get_workflow_statistics()

        if workflow_stats:
            console.print("\n[bold]Workflow Statistics:[/bold]")

            # Create workflow stats table
            table = Table(
                "Workflow",
                "Total Runs",
                "OK",
                "NOK",
                "Running",
                "Aborted",
                "Latest Run",
            )

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
                    stats["latest_run"] or "N/A",
                )

            console.print(table)

        # Show node statistics
        node_stats = stats_service.get_node_statistics()

        if node_stats:
            console.print("\n[bold]Node Statistics:[/bold]")

            # Create node stats table
            table = Table(
                "Workflow", "Node", "OK", "NOK", "Skipped", "Pending", "Running"
            )

            for key, stats in node_stats.items():
                status_counts = stats["status_counts"]

                table.add_row(
                    stats["workflow_name"],
                    stats["node_id"],
                    str(status_counts.get("ok", 0)),
                    str(status_counts.get("nok", 0)),
                    str(status_counts.get("skipped", 0)),
                    str(status_counts.get("pending", 0)),
                    str(status_counts.get("running", 0)),
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
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
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
            run = run_repo.get_run(workflow, run_id)

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
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    for logger_name in ("botocore", "boto3", "urllib3"):
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
