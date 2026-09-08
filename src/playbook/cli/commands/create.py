"""Create a schema-v3 runbook."""

import re
from pathlib import Path

import tomlkit
import typer
from rich.prompt import Confirm, Prompt

from ...domain.exceptions import FileOperationError
from ..common import console, handle_error_and_exit


def create(
    ctx: typer.Context,
    title: str | None = typer.Option(None, "--title", help="Runbook title"),
    author: str | None = typer.Option(None, "--author", help="Author name"),
    description: str | None = typer.Option(
        None,
        "--description",
        help="Runbook description",
    ),
    output: Path | None = typer.Option(None, "--output", help="Output file path"),
) -> None:
    """Create an ordered runbook interactively."""
    try:
        _create_runbook(title, author, description, output)
    except Exception as error:
        handle_error_and_exit(
            error,
            "Runbook creation",
            ctx.params.get("verbose", False),
        )


def _create_runbook(
    title: str | None,
    author: str | None,
    description: str | None,
    output: Path | None,
) -> None:
    title = title or Prompt.ask("Enter runbook title")
    author = author or Prompt.ask("Enter author name")
    description = description or Prompt.ask(
        "Enter runbook description",
        default=f"Runbook for {title}",
    )
    workflow_id = _slug(title)
    if output is None:
        output = Path(
            Prompt.ask(
                "Enter output file path",
                default=f"{workflow_id}.playbook.toml",
            )
        )
    if output.exists() and not Confirm.ask(f"File {output} already exists. Overwrite?"):
        return

    document = tomlkit.document()
    document.add("schema_version", tomlkit.item(3))
    document.add(tomlkit.nl())
    metadata = tomlkit.table()
    metadata.add("id", workflow_id)
    metadata.add("title", title)
    metadata.add("description", description)
    metadata.add("version", "0.1.0")
    metadata.add("author", author)
    document.add("runbook", metadata)
    steps = tomlkit.aot()

    if Confirm.ask("Add workflow steps?", default=True):
        while True:
            steps.append(_prompt_for_step())
            if not Confirm.ask("Add another step?", default=True):
                break

    document.add(tomlkit.nl())
    document.add("steps", steps if steps else tomlkit.item([]))
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(tomlkit.dumps(document))
    except OSError as error:
        raise FileOperationError(
            f"Failed to create runbook file: {error}",
            suggestion="Check the path and file permissions",
        ) from error
    console.print(f"Created new runbook at {output}")
    console.print("Run 'playbook validate' before executing it.")


def _prompt_for_step():
    step_type = Prompt.ask(
        "Step type",
        choices=["manual", "command", "function"],
        default="manual",
    )
    step = tomlkit.table()
    step.add("id", Prompt.ask("Step ID"))
    step.add("type", step_type)
    name = Prompt.ask("Step name", default="")
    if name:
        step.add("name", name)
    instructions = Prompt.ask("Instructions", default="")
    if instructions:
        step.add("instructions", instructions)

    if step_type == "manual":
        step.add("prompt", Prompt.ask("Completion prompt", default="Done?"))
    elif step_type == "command":
        step.add("command", Prompt.ask("Command"))
        if Confirm.ask("Interactive command?", default=False):
            step.add("interactive", True)
        step.add(
            "timeout_seconds",
            int(Prompt.ask("Timeout in seconds", default="300")),
        )
        verify = Prompt.ask("Verification prompt", default="")
        if verify:
            step.add("verify", verify)
    else:
        step.add("plugin", Prompt.ask("Plugin", default="python"))
        step.add("function", Prompt.ask("Function"))
        if Confirm.ask("Add plugin parameters later?", default=True):
            step.add("params", {})
        verify = Prompt.ask("Verification prompt", default="")
        if verify:
            step.add("verify", verify)

    step.add("required", Confirm.ask("Required step?", default=True))
    return step


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workflow"
