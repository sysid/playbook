# src/playbook/cli/common.py
"""Common utilities for CLI commands."""

import logging
import sys
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from .error_handler import ErrorHandler
from ..infrastructure.parser import RunbookParser
from ..infrastructure.persistence import (
    SQLiteRunRepository,
    SQLiteNodeExecutionRepository,
)
from ..infrastructure.process import ShellProcessRunner
from ..infrastructure.variables import VariableManager
from ..service.engine import RunbookEngine
from .interaction.handlers import ConsoleNodeIOHandler, SystemClock
from ..domain.ports import NodeIOHandler

logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


def get_engine(
    state_path: str | None = None,
    io_handler: NodeIOHandler | None = None,
    max_attempts: int = 3,
) -> RunbookEngine:
    """Create and configure the runbook engine"""
    db_path = str(Path(state_path or "~/.config/playbook/run.db").expanduser())

    logger.debug(f"Using state path: {db_path}")

    # Create dependencies
    clock = SystemClock()
    process_runner = ShellProcessRunner()
    run_repo = SQLiteRunRepository(db_path)
    node_repo = SQLiteNodeExecutionRepository(db_path)

    # Create engine
    return RunbookEngine(
        clock=clock,
        process_runner=process_runner,
        run_repo=run_repo,
        node_repo=node_repo,
        io_handler=io_handler or ConsoleNodeIOHandler(console),
        max_attempts=max_attempts,
    )


def get_parser(interactive: bool = True) -> RunbookParser:
    """Get a runbook parser instance with variable support"""
    variable_manager = VariableManager(interactive=interactive)
    return RunbookParser(variable_manager=variable_manager)


def get_variable_manager(interactive: bool = True) -> VariableManager:
    """Get a variable manager instance"""
    return VariableManager(interactive=interactive)


def get_error_handler(debug: bool = False) -> ErrorHandler:
    """Get an error handler instance"""
    return ErrorHandler(console, debug)


def handle_error_and_exit(
    error: Exception,
    context: str | None = None,
    debug: bool = False,
) -> None:
    """Handle an error and exit with appropriate code"""
    error_handler = get_error_handler(debug)
    exit_code = error_handler.handle_error(error, context)
    sys.exit(exit_code)


def safe_execute(
    func: Callable[..., Any],
    *args: Any,
    context: str | None = None,
    debug: bool = False,
    **kwargs: Any,
) -> Any:
    """Execute a function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error_and_exit(e, context, debug)
