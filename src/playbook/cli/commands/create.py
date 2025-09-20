# src/playbook/cli/commands/create.py
"""Create command implementation."""

import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm, Prompt

from ..common import console, handle_error_and_exit
from ...domain.exceptions import FileOperationError


def create(
    ctx: typer.Context,
    title: str = typer.Option(None, "--title", help="Runbook title"),
    author: str = typer.Option(None, "--author", help="Author name"),
    description: str = typer.Option(None, "--description", help="Runbook description"),
    output: Optional[Path] = typer.Option(None, "--output", help="Output file path"),
):
    """Create a new runbook file interactively"""
    try:
        _create_runbook(title, author, description, output)
    except Exception as e:
        handle_error_and_exit(e, "Runbook creation", ctx.params.get("verbose", False))


def _create_runbook(
    title: Optional[str],
    author: Optional[str],
    description: Optional[str],
    output: Optional[Path],
) -> None:
    """Internal runbook creation logic"""
    # Get inputs interactively if not provided
    if title is None:
        title = Prompt.ask("Enter runbook title")

    if author is None:
        author = Prompt.ask("Enter author name")

    if description is None:
        description = Prompt.ask(
            "Enter runbook description", default=f"Runbook for {title}"
        )

    # Set default output path if none provided
    if output is None:
        default_filename = f"{title.lower().replace(' ', '_')}.playbook.toml"
        output_str = Prompt.ask("Enter output file path", default=default_filename)
        output = Path(output_str)

    # Check if file exists
    if output.exists():
        if not Confirm.ask(f"File {output} already exists. Overwrite?"):
            return

    # Create a template with runbook metadata
    now = datetime.datetime.now(datetime.timezone.utc)

    # Start with the basic runbook metadata
    template = f"""[runbook]
title       = "{title}"
description = "{description}"
version     = "0.1.0"
author      = "{author}"
created_at  = "{now.isoformat()}"
"""

    # Ask if user wants to add nodes
    nodes = []
    if Confirm.ask("Do you want to add manual nodes to your runbook?", default=True):
        previous_node_id = None
        node_counter = 1

        # Interactive loop to add manual nodes
        while True:
            console.print("\n[bold blue]Adding a Manual Node[/bold blue]")

            # Get node ID with default based on count
            default_node_id = f"node{node_counter}"
            node_id = Prompt.ask("Enter node ID", default=default_node_id)

            # Get node name (optional)
            node_name = Prompt.ask("Enter node name (optional)", default="")

            # Get node description
            default_description = f"Step {node_counter} of the workflow"
            node_description = Prompt.ask(
                "Enter node description", default=default_description
            )

            # Get prompt after
            prompt_after = Prompt.ask(
                "Enter prompt after message", default="Continue with the next step?"
            )

            # Get dependencies - default to previous node if exists
            default_deps = f'"{previous_node_id}"' if previous_node_id else ""
            depends_on_str = Prompt.ask(
                "Enter dependencies (comma-separated IDs)", default=default_deps
            )

            # Parse dependencies from string
            depends_on = []
            if depends_on_str:
                # Handle both quoted and unquoted node IDs
                for dep in depends_on_str.split(","):
                    dep = dep.strip().strip("\"'")
                    if dep:  # Skip empty strings
                        depends_on.append(dep)

            # Get critical flag
            critical = Confirm.ask(
                "Is this node critical? (Failure will abort the workflow)",
                default=False,
            )

            # Build node configuration
            node = {
                "id": node_id,
                "name": node_name if node_name != node_id.capitalize() else None,
                "description": node_description,
                "prompt_after": prompt_after,
                "depends_on": depends_on,
                "critical": critical,
                "type": "Manual",
            }

            nodes.append(node)

            # Update for next iteration
            previous_node_id = node_id
            node_counter += 1

            # Ask if user wants to add another node
            if not Confirm.ask("Add another node?", default=True):
                break

        # Add nodes to template
        for node in nodes:
            node_section = f"""
[{node["id"]}]
type         = "{node["type"]}"
"""
            if node["name"]:
                node_section += f'name         = "{node["name"]}"\n'

            node_section += f'description  = """{node["description"]}"""\n'
            node_section += f'prompt_after = "{node["prompt_after"]}"\n'

            if node["depends_on"]:
                depends_str = ", ".join([f'"{dep}"' for dep in node["depends_on"]])
                node_section += f"depends_on   = [{depends_str}]\n"
            else:
                node_section += "depends_on   = []\n"

            node_section += f"critical     = {str(node['critical']).lower()}\n"

            template += node_section

    # Add example nodes as comments if no manual nodes were added
    if not any(node["type"] == "Manual" for node in nodes):
        template += """
# Example manual node - uncomment to use
# [approve]
# type         = "Manual"
# prompt_after = "Proceed with deployment?"
# description  = \"\"\"This step requires manual approval before proceeding.
# Please review the changes and confirm.\"\"\"
# depends_on  = []
# critical    = true

# Example command node - uncomment to use
# [build]
# type         = "Command"
# command_name = "echo 'Hello, World!'"
# description  = "Builds the project artifacts"
# depends_on   = []
# timeout      = 300
# name         = "Build step"
# skip         = true

# Example function node - uncomment to use
# [notify]
# type           = "Function"
# function_name  = "playbook.functions.notify"
# function_params = {{ "message" = "Deployment complete" }}
# description    = "Sends deployment completion notification"
# depends_on     = []
"""

    # Write the template to file
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(template)
    except PermissionError:
        raise FileOperationError(
            f"Permission denied writing to: {output}",
            suggestion="Check file permissions or try a different location",
        )
    except Exception as e:
        raise FileOperationError(
            f"Failed to create runbook file: {str(e)}",
            context={"output_path": str(output)},
            suggestion="Check disk space and file permissions",
        )

    console.print(f"[bold green]Created new runbook at {output}[/bold green]")
    console.print("\nEdit this file to add more nodes or customize the workflow.")
    console.print("Use 'playbook validate' to check your runbook for correctness.")
