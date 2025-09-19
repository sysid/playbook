# src/playbook/cli/error_handler.py
"""Error handling utilities for CLI."""

import traceback

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..domain.exceptions import (
    PlaybookError,
    ConfigurationError,
    ParseError,
    ValidationError,
    ExecutionError,
    NodeExecutionError,
    CommandExecutionError,
    FunctionExecutionError,
    PersistenceError,
    DependencyError,
    TimeoutError,
)


class ErrorHandler:
    """Handles error formatting and display for CLI."""

    def __init__(self, console: Console, debug: bool = False):
        self.console = console
        self.debug = debug

    def handle_error(self, error: Exception, context: str = None) -> int:
        """Handle an error and return appropriate exit code."""
        if isinstance(error, PlaybookError):
            return self._handle_playbook_error(error, context)
        else:
            return self._handle_unexpected_error(error, context)

    def _handle_playbook_error(self, error: PlaybookError, context: str = None) -> int:
        """Handle known Playbook errors with specific formatting."""

        # Determine error styling based on type
        if isinstance(error, (ConfigurationError, DependencyError)):
            style = "red"
            icon = "❌"
            exit_code = 2
        elif isinstance(error, (ParseError, ValidationError)):
            style = "yellow"
            icon = "⚠️"
            exit_code = 1
        elif isinstance(error, ExecutionError):
            style = "red"
            icon = "🚫"
            exit_code = 1
        elif isinstance(error, PersistenceError):
            style = "magenta"
            icon = "💾"
            exit_code = 3
        else:
            style = "red"
            icon = "❌"
            exit_code = 1

        # Build error message
        title = f"{icon} {error.__class__.__name__}"

        # Create main error content
        content = Text()
        content.append(f"{error.message}\n", style=style)

        # Add context if available
        if context:
            content.append(f"\nContext: {context}\n", style="dim")

        # Add error-specific context
        if hasattr(error, 'context') and error.context:
            content.append("\nDetails:\n", style="bold")
            for key, value in error.context.items():
                content.append(f"  {key}: {value}\n", style="dim")

        # Add node-specific information
        if isinstance(error, NodeExecutionError):
            content.append(f"\nNode: {error.node_id}", style="cyan")
            if error.node_type:
                content.append(f" ({error.node_type})", style="dim cyan")
            content.append("\n")

            # Add command-specific info
            if isinstance(error, CommandExecutionError):
                content.append(f"Command: {error.command}\n", style="dim")
                if error.exit_code is not None:
                    content.append(f"Exit Code: {error.exit_code}\n", style="dim")
                if error.stderr:
                    content.append(f"Error Output: {error.stderr}\n", style="dim red")

            # Add function-specific info
            elif isinstance(error, FunctionExecutionError):
                content.append(f"Function: {error.function_name}\n", style="dim")

        # Add timeout-specific info
        if isinstance(error, TimeoutError):
            content.append(f"Timeout: {error.timeout_seconds}s\n", style="dim")

        # Add suggestion if available
        if hasattr(error, 'suggestion') and error.suggestion:
            content.append(f"\n💡 Suggestion: {error.suggestion}", style="green")

        # Display the error panel
        panel = Panel(
            content,
            title=title,
            border_style=style,
            expand=False
        )

        self.console.print(panel)

        # Show debug info if requested
        if self.debug:
            self._show_debug_info(error)

        return exit_code

    def _handle_unexpected_error(self, error: Exception, context: str = None) -> int:
        """Handle unexpected errors."""
        title = "🐛 Unexpected Error"

        content = Text()
        content.append(f"{error.__class__.__name__}: {str(error)}\n", style="red")

        if context:
            content.append(f"\nContext: {context}\n", style="dim")

        content.append("\nThis appears to be an unexpected error. ", style="yellow")
        content.append("Please report this issue with the following details:", style="yellow")

        panel = Panel(
            content,
            title=title,
            border_style="red",
            expand=False
        )

        self.console.print(panel)

        # Always show debug info for unexpected errors
        self._show_debug_info(error)

        return 1

    def _show_debug_info(self, error: Exception):
        """Show debug information including traceback."""
        self.console.print("\n[dim]Debug Information:[/dim]")
        self.console.print("[dim]" + "=" * 50 + "[/dim]")

        # Get traceback
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        self.console.print(f"[dim]{tb_str}[/dim]")

    def format_validation_errors(self, errors: list[str]) -> None:
        """Format validation errors in a user-friendly way."""
        if not errors:
            return

        content = Text()
        content.append("The following validation errors were found:\n\n", style="yellow")

        for i, error in enumerate(errors, 1):
            content.append(f"{i}. {error}\n", style="red")

        content.append("\n💡 Fix these issues and try again.", style="green")

        panel = Panel(
            content,
            title="⚠️ Validation Errors",
            border_style="yellow",
            expand=False
        )

        self.console.print(panel)

    def format_suggestions(self, suggestions: list[str]) -> None:
        """Format helpful suggestions."""
        if not suggestions:
            return

        content = Text()
        content.append("Here are some suggestions:\n\n", style="green")

        for i, suggestion in enumerate(suggestions, 1):
            content.append(f"💡 {suggestion}\n", style="green")

        panel = Panel(
            content,
            title="Helpful Suggestions",
            border_style="green",
            expand=False
        )

        self.console.print(panel)