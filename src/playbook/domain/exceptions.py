# src/playbook/domain/exceptions.py
"""Custom exception hierarchy for Playbook."""

from typing import Dict, Any, Optional


class PlaybookError(Exception):
    """Base exception for all Playbook-related errors."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.suggestion = suggestion


class ConfigurationError(PlaybookError):
    """Raised when there are configuration-related issues."""

    pass


class ParseError(PlaybookError):
    """Raised when parsing runbook files fails."""

    pass


class ValidationError(PlaybookError):
    """Raised when runbook validation fails."""

    pass


class ExecutionError(PlaybookError):
    """Raised when workflow execution fails."""

    pass


class NodeExecutionError(ExecutionError):
    """Raised when a specific node execution fails."""

    def __init__(
        self,
        message: str,
        node_id: str,
        node_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message, context, suggestion)
        self.node_id = node_id
        self.node_type = node_type


class CommandExecutionError(NodeExecutionError):
    """Raised when command execution fails."""

    def __init__(
        self,
        message: str,
        node_id: str,
        command: str,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message, node_id, "Command", context, suggestion)
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class FunctionExecutionError(NodeExecutionError):
    """Raised when function execution fails."""

    def __init__(
        self,
        message: str,
        node_id: str,
        function_name: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message, node_id, "Function", context, suggestion)
        self.function_name = function_name


class PersistenceError(PlaybookError):
    """Raised when database operations fail."""

    pass


class DependencyError(PlaybookError):
    """Raised when external dependencies are missing or misconfigured."""

    pass


class SystemDependencyError(DependencyError):
    """Raised when required system dependencies are missing."""

    pass


class DatabaseError(PersistenceError):
    """Raised when database operations fail."""

    pass


class FileOperationError(PlaybookError):
    """Raised when file operations fail."""

    pass


class TimeoutError(ExecutionError):
    """Raised when operations timeout."""

    def __init__(
        self,
        message: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message, context, suggestion)
        self.timeout_seconds = timeout_seconds
