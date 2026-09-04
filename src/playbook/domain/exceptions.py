"""Exceptions exposed by the current Playbook CLI."""


class PlaybookError(Exception):
    def __init__(self, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


class ConfigurationError(PlaybookError):
    """Invalid CLI or variable configuration."""


class ParseError(PlaybookError):
    """A runbook cannot be parsed."""


class ValidationError(PlaybookError):
    """A runbook or variable value is invalid."""


class FileOperationError(PlaybookError):
    """A requested file operation failed."""
