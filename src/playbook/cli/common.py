# src/playbook/cli/common.py
"""Common utilities for CLI commands."""

import logging
import sys
from typing import Optional

from rich.console import Console

from ..config import config_manager
from .error_handler import ErrorHandler
from ..infrastructure.parser import RunbookParser
from ..infrastructure.persistence import (
    SQLiteRunRepository,
    SQLiteNodeExecutionRepository,
)
from ..infrastructure.process import ShellProcessRunner
from ..infrastructure.variables import VariableManager
from ..service.engine import RunbookEngine
from .interaction.handlers import SystemClock
from ..domain.ports import NodeIOHandler

logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


def get_engine(
    state_path: Optional[str] = None, io_handler: Optional[NodeIOHandler] = None
) -> RunbookEngine:
    """Create and configure the runbook engine"""
    # Load configuration
    config = config_manager.get_config()

    # Override state path if provided
    db_path = state_path or config.database.path

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
        io_handler=io_handler,
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
    error: Exception, context: str = None, debug: bool = False
) -> None:
    """Handle an error and exit with appropriate code"""
    error_handler = get_error_handler(debug)
    exit_code = error_handler.handle_error(error, context)
    sys.exit(exit_code)


def safe_execute(func, *args, context: str = None, debug: bool = False, **kwargs):
    """Execute a function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error_and_exit(e, context, debug)
