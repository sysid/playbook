# src/playbook/cli/commands/run.py
"""Run and resume command implementations."""

from pathlib import Path
from typing import Optional, List

import typer
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt

from ..common import (
    console,
    get_engine,
    get_parser,
    get_variable_manager,
    handle_error_and_exit,
)
from ..interaction.handlers import ConsoleNodeIOHandler
from ...domain.models import (
    NodeStatus,
    RunStatus,
    Runbook,
    RunInfo,
    TriggerType,
)
from ...domain.exceptions import ParseError, ExecutionError


def run(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
    max_retries: int = typer.Option(
        3, "--max-retries", help="Maximum retry attempts per failed node"
    ),
    var: Optional[List[str]] = typer.Option(
        None, "--var", help="Set variable in KEY=VALUE format"
    ),
    vars_file: Optional[str] = typer.Option(
        None, "--vars-file", help="Load variables from file"
    ),
    vars_env: Optional[str] = typer.Option(
        "PLAYBOOK_VAR_",
        "--vars-env",
        help="Environment variable prefix for loading variables",
    ),
    no_interactive_vars: bool = typer.Option(
        False,
        "--no-interactive-vars",
        help="Don't prompt for missing required variables",
    ),
):
    """Run a playbook from start to finish"""
    try:
        # Process variables
        variables = _collect_variables(
            var, vars_file, vars_env, not no_interactive_vars
        )

        parser = get_parser(interactive=not no_interactive_vars)
        _execute_workflow(
            parser, file, state_path, variables=variables, max_retries=max_retries
        )
    except Exception as e:
        handle_error_and_exit(e, "Runbook execution", ctx.params.get("verbose", False))


def resume(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    run_id: int = typer.Argument(..., help="Run ID to resume"),
    node_id: Optional[str] = typer.Option(
        None, "--node", help="Node ID to resume from"
    ),
    state_path: Optional[str] = typer.Option(
        None, "--state-path", help="State database path"
    ),
    max_retries: int = typer.Option(
        3, "--max-retries", help="Maximum retry attempts per failed node"
    ),
    var: Optional[List[str]] = typer.Option(
        None, "--var", help="Set variable in KEY=VALUE format"
    ),
    vars_file: Optional[str] = typer.Option(
        None, "--vars-file", help="Load variables from file"
    ),
    vars_env: Optional[str] = typer.Option(
        "PLAYBOOK_VAR_",
        "--vars-env",
        help="Environment variable prefix for loading variables",
    ),
    no_interactive_vars: bool = typer.Option(
        False,
        "--no-interactive-vars",
        help="Don't prompt for missing required variables",
    ),
):
    """Resume a previously started run"""
    try:
        # Process variables
        variables = _collect_variables(
            var, vars_file, vars_env, not no_interactive_vars
        )

        parser = get_parser(interactive=not no_interactive_vars)
        _execute_workflow(
            parser, file, state_path, run_id, node_id, max_retries, variables=variables
        )
    except Exception as e:
        handle_error_and_exit(e, "Runbook resume", ctx.params.get("verbose", False))


def _collect_variables(
    var: Optional[List[str]], vars_file: Optional[str], vars_env: str, interactive: bool
) -> dict:
    """Collect variables from all sources."""
    var_manager = get_variable_manager(interactive=interactive)

    # Collect from different sources
    cli_vars = {}
    file_vars = {}
    env_vars = {}

    # CLI variables
    if var:
        cli_vars = var_manager.parse_cli_variables(var)

    # File variables
    if vars_file:
        file_vars = var_manager.load_variables_from_file(vars_file)

    # Environment variables
    if vars_env:
        env_vars = var_manager.load_variables_from_env(vars_env)

    # Merge with priority
    return var_manager.merge_variables(
        cli_vars=cli_vars, file_vars=file_vars, env_vars=env_vars
    )


def _execute_workflow(
    parser,
    file: Path,
    state_path: Optional[str] = None,
    run_id: Optional[int] = None,
    start_node_id: Optional[str] = None,
    max_retries: int = 3,
    variables: Optional[dict] = None,
) -> None:
    """
    Shared workflow execution logic for both run and resume commands
    """
    # Parse runbook
    console.print(f"Parsing runbook: {file}")
    try:
        runbook = parser.parse(str(file), variables=variables)
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

    # Create progress display and IO handler
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeElapsedColumn(),
    )
    io_handler = ConsoleNodeIOHandler(console, progress)
    engine = get_engine(state_path, io_handler)

    # Initialize run info based on whether we're resuming or starting fresh
    try:
        if run_id is not None:
            console.print(f"Resuming run: {runbook.title} (Run ID: {run_id})")
            run_info = engine.resume_run(runbook, run_id, start_node_id)
        else:
            console.print(f"Starting run: {runbook.title}")
            run_info = engine.start_run(runbook)
            console.print(f"Run ID: {run_info.run_id}")
    except Exception as e:
        raise ExecutionError(
            f"Failed to initialize workflow execution: {str(e)}",
            context={"runbook": runbook.title, "run_id": run_id},
            suggestion="Check database connectivity and ensure the run ID exists",
        )

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
    _execute_nodes(
        engine,
        runbook,
        run_info,
        nodes_to_run,
        progress,
        io_handler,
        max_retries,
        variables,
    )


def _determine_nodes_to_run(
    engine,
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
            raise ExecutionError(
                f"Start node '{start_node_id}' not found in runbook",
                context={"available_nodes": list(order)},
                suggestion="Check the node ID and ensure it exists in the runbook",
            )

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
    engine,
    runbook: Runbook,
    run_info: RunInfo,
    nodes_to_run: List[str],
    progress: Progress,
    io_handler: ConsoleNodeIOHandler,
    max_retries: int = 3,
    variables: Optional[dict] = None,
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

            # Add empty lines before each node
            console.print()
            console.print()

            # Update progress bar with current node
            progress.start()
            progress.update(task, description=f"{node_display_name}")
            progress.stop()
            # noinspection PyTypeChecker
            io_handler.display_node_header(node.id, node.name, node.type.value)
            # Hide the progress bar during execution to prevent duplicate display

            # Check if this node has an existing execution record
            existing_execution = existing_executions_map.get(current_node_id)

            # Execute node based on whether it has an existing execution
            if existing_execution and existing_execution.status != NodeStatus.OK:
                # Resume with existing record
                status, execution = engine.resume_node_execution(
                    runbook, current_node_id, run_info, existing_execution, variables
                )
            else:
                # Create new execution record (for fresh nodes)
                status, execution = engine.execute_node(
                    runbook, current_node_id, run_info, variables
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

                # Handle node failure with retry loop
                node_completed = False

                # Interactive failure handling loop
                while not node_completed:
                    # Show error details
                    if execution.exception:
                        console.print(
                            f"[bold red]Error:[/bold red] {execution.exception}"
                        )

                    if execution.stderr:
                        console.print(
                            f"[bold red]stderr:[/bold red]\n{execution.stderr}"
                        )

                    # Get current attempt number for this node
                    latest_execution = engine.node_repo.get_latest_execution_attempt(
                        runbook.title, run_info.run_id, current_node_id
                    )
                    current_attempt = (
                        latest_execution.attempt if latest_execution else 0
                    )

                    # If max retries reached, only allow skip/abort
                    if current_attempt >= max_retries:
                        if node.critical:
                            console.print(
                                f"[bold red]Critical node failed after {max_retries} attempts. Aborting.[/bold red]"
                            )
                            run_info.status = RunStatus.ABORTED
                            engine.run_repo.update_run(run_info)
                            node_completed = True
                            break
                        else:
                            prompt_text = f"Node failed. Maximum retries ({max_retries}) reached. Skip (s) or Abort (a)?"
                            choices = ["s", "a"]
                            default = "a"
                            progress.stop()  # Hide progress bar for user interaction
                            choice = Prompt.ask(
                                prompt_text, choices=choices, default=default
                            )

                            if choice == "s":
                                console.print("Skipping node")
                                execution.status = NodeStatus.SKIPPED
                                engine.node_repo.update_execution(execution)
                                progress.update(
                                    task,
                                    description=f"Skipped: {node_display_name}",
                                    advance=1,
                                )
                                node_completed = True
                            else:  # choice == "a"
                                console.print("Aborting run")
                                run_info.status = RunStatus.ABORTED
                                engine.run_repo.update_run(run_info)
                                node_completed = True
                                break
                    else:
                        # Still have retries available
                        prompt_text = f"Node failed (attempt {current_attempt}/{max_retries}). Retry (r), Skip (s), or Abort (a)?"
                        choices = ["r", "s", "a"]
                        default = "r"

                        # Ask user what to do
                        progress.stop()  # Hide progress bar for user interaction
                        choice = Prompt.ask(
                            prompt_text, choices=choices, default=default
                        )

                        if choice == "r":
                            next_attempt = current_attempt + 1
                            console.print(
                                f"Retrying node '{current_node_id}' (attempt {next_attempt}/{max_retries})..."
                            )

                            # Execute single retry attempt creating a new execution record
                            status, execution = engine.execute_node_retry(
                                runbook,
                                current_node_id,
                                run_info,
                                next_attempt,
                                variables,
                            )

                            if status == NodeStatus.OK:
                                console.print(
                                    f"[bold green]Node '{current_node_id}' succeeded on attempt {next_attempt}[/bold green]"
                                )
                                progress.update(
                                    task,
                                    description=f"Completed: {node_display_name}",
                                    advance=1,
                                )
                                node_completed = True
                            else:
                                console.print(
                                    f"[bold red]Retry attempt {next_attempt} failed[/bold red]"
                                )
                                # Loop will continue with updated attempt count

                        elif choice == "s":
                            if node.critical:
                                console.print(
                                    "[bold red]Cannot skip critical node[/bold red]"
                                )
                                # Loop will continue to prompt user again
                            else:
                                console.print("Skipping node")
                                execution.status = NodeStatus.SKIPPED
                                engine.node_repo.update_execution(execution)
                                progress.update(
                                    task,
                                    description=f"Skipped: {node_display_name}",
                                    advance=1,
                                )
                                node_completed = True

                        elif choice == "a":
                            console.print("Aborting run")
                            run_info.status = RunStatus.ABORTED
                            engine.run_repo.update_run(run_info)
                            node_completed = True
                            break

                # Break out of main node loop if run was aborted
                if run_info.status == RunStatus.ABORTED:
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
