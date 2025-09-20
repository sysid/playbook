# src/playbook/cli/commands/validate.py
"""Validate command implementation."""

from pathlib import Path
from typing import Optional, List

import typer

from ..common import console, get_engine, get_parser, get_variable_manager, handle_error_and_exit
from ...domain.models import NodeType
from ...domain.exceptions import ParseError, ValidationError


def validate(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    strict: bool = typer.Option(False, "--strict", help="Enable strict validation"),
    check_vars: bool = typer.Option(False, "--check-vars", help="Show variable information"),
    var: Optional[List[str]] = typer.Option(
        None, "--var", help="Set variable in KEY=VALUE format"
    ),
    vars_file: Optional[str] = typer.Option(
        None, "--vars-file", help="Load variables from file"
    ),
    vars_env: Optional[str] = typer.Option(
        "PLAYBOOK_VAR_", "--vars-env", help="Environment variable prefix for loading variables"
    ),
):
    """Validate a runbook file"""
    try:
        parser = get_parser(interactive=False)  # No interactive prompts in validation
        engine = get_engine()

        # Process variables if provided
        variables = {}
        variable_definitions = {}

        if check_vars or var or vars_file or vars_env:
            # Get variable definitions from the file
            try:
                variable_definitions = parser.get_variable_definitions(str(file))
            except FileNotFoundError:
                raise ParseError(
                    f"Runbook file not found: {file}",
                    suggestion="Check the file path and ensure the file exists"
                )

            if check_vars:
                _display_variable_information(variable_definitions)
                if not (var or vars_file or vars_env):
                    return  # Only show variable info, don't validate

            if var or vars_file or vars_env:
                # Collect variables
                variables = _collect_variables(var, vars_file, vars_env)

        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        try:
            runbook = parser.parse(str(file), variables=variables)
        except FileNotFoundError:
            raise ParseError(
                f"Runbook file not found: {file}",
                suggestion="Check the file path and ensure the file exists"
            )
        except Exception as e:
            raise ParseError(
                f"Failed to parse runbook: {str(e)}",
                context={"file": str(file)},
                suggestion="Check the TOML syntax and ensure all required fields are present"
            )

        # Validate runbook
        console.print("Validating runbook...")
        errors = engine.validate(runbook)

        if errors:
            # Use error handler for validation errors
            from ..error_handler import ErrorHandler
            error_handler = ErrorHandler(console, ctx.params.get('verbose', False))
            error_handler.format_validation_errors(errors)
            raise ValidationError(
                f"Found {len(errors)} validation error(s)",
                context={"errors": errors, "file": str(file)},
                suggestion="Fix the validation errors and try again"
            )
        else:
            console.print("[bold green]✅ Runbook is valid![/bold green]")

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

            skipped_count = sum(1 for n in runbook.nodes.values() if n.skip)
            console.print(f"  • Skipped nodes: {skipped_count}")

            # Show helpful suggestions for improvement
            suggestions = []
            if skipped_count > 0:
                suggestions.append("Consider reviewing skipped nodes to ensure they're intentionally disabled")
            if len(runbook.nodes) > 20:
                suggestions.append("Large runbooks may benefit from being split into smaller, focused workflows")

            if suggestions:
                from ..error_handler import ErrorHandler
                error_handler = ErrorHandler(console, False)
                error_handler.format_suggestions(suggestions)

    except Exception as e:
        handle_error_and_exit(e, "Runbook validation", ctx.params.get('verbose', False))


def _collect_variables(
    var: Optional[List[str]],
    vars_file: Optional[str],
    vars_env: str
) -> dict:
    """Collect variables from all sources."""
    var_manager = get_variable_manager(interactive=False)

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
        cli_vars=cli_vars,
        file_vars=file_vars,
        env_vars=env_vars
    )


def _display_variable_information(variable_definitions: dict) -> None:
    """Display information about variables defined in the workflow."""
    if not variable_definitions:
        console.print("[yellow]No variables defined in this workflow[/yellow]")
        return

    console.print(f"\n[bold]Variables ({len(variable_definitions)}):[/bold]")

    required_vars = []
    optional_vars = []

    for name, definition in variable_definitions.items():
        if definition.required:
            required_vars.append((name, definition))
        else:
            optional_vars.append((name, definition))

    if required_vars:
        console.print(f"\n[bold red]Required variables ({len(required_vars)}):[/bold red]")
        for name, definition in required_vars:
            _display_variable_details(name, definition)

    if optional_vars:
        console.print(f"\n[bold blue]Optional variables ({len(optional_vars)}):[/bold blue]")
        for name, definition in optional_vars:
            _display_variable_details(name, definition)


def _display_variable_details(name: str, definition) -> None:
    """Display detailed information about a single variable."""
    details = []

    # Type
    if definition.type != "string":
        details.append(f"type: {definition.type}")

    # Default value
    if definition.default is not None:
        if isinstance(definition.default, str):
            details.append(f"default: '{definition.default}'")
        else:
            details.append(f"default: {definition.default}")

    # Choices
    if definition.choices:
        choices_str = ", ".join(str(c) for c in definition.choices)
        details.append(f"choices: [{choices_str}]")

    # Constraints
    if definition.min is not None:
        details.append(f"min: {definition.min}")
    if definition.max is not None:
        details.append(f"max: {definition.max}")
    if definition.pattern:
        details.append(f"pattern: {definition.pattern}")

    # Format output
    if details:
        details_str = f" ({', '.join(details)})"
    else:
        details_str = ""

    description = f" - {definition.description}" if definition.description else ""

    console.print(f"  • [bold]{name}[/bold]{details_str}{description}")
