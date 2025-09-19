# src/playbook/cli/commands/validate.py
"""Validate command implementation."""

from pathlib import Path

import typer

from ..common import console, get_engine, get_parser, handle_error_and_exit
from ...domain.models import NodeType
from ...domain.exceptions import ParseError, ValidationError


def validate(
    ctx: typer.Context,
    file: Path = typer.Argument(..., help="Runbook file path"),
    strict: bool = typer.Option(False, "--strict", help="Enable strict validation"),
):
    """Validate a runbook file"""
    try:
        parser = get_parser()
        engine = get_engine()

        # Parse runbook
        console.print(f"Parsing runbook: {file}")
        try:
            runbook = parser.parse(str(file))
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
