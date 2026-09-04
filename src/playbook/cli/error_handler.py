"""Consistent, emoji-free CLI error output."""

import traceback

from rich.console import Console
from rich.panel import Panel

from ..domain.exceptions import (
    ConfigurationError,
    ParseError,
    PlaybookError,
    ValidationError,
)


class ErrorHandler:
    def __init__(self, console: Console, debug: bool = False) -> None:
        self.console = console
        self.debug = debug

    def handle_error(self, error: Exception, context: str | None = None) -> int:
        if isinstance(error, PlaybookError):
            message = error.message
            if error.suggestion:
                message += f"\n\nSuggestion: {error.suggestion}"
            title = error.__class__.__name__
            exit_code = self._exit_code(error)
        else:
            message = f"{error.__class__.__name__}: {error}"
            title = "Unexpected error"
            exit_code = 1
        if context:
            message += f"\n\nContext: {context}"
        self.console.print(Panel(message, title=title, border_style="red"))
        if self.debug:
            self.console.print(
                "".join(
                    traceback.format_exception(
                        type(error),
                        error,
                        error.__traceback__,
                    )
                )
            )
        return exit_code

    @staticmethod
    def _exit_code(error: PlaybookError) -> int:
        if isinstance(error, ConfigurationError):
            return 2
        if isinstance(error, (ParseError, ValidationError)):
            return 1
        return 1
