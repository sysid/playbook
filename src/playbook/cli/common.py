# src/playbook/cli/common.py
"""Common utilities for CLI commands."""

import logging
import sys
from typing import Optional

from rich.console import Console

from ..config import load_config
from .error_handler import ErrorHandler
from ..infrastructure.functions import PythonFunctionLoader
from ..infrastructure.parser import RunbookParser
from ..infrastructure.persistence import (
    SQLiteRunRepository,
    SQLiteNodeExecutionRepository,
)
from ..infrastructure.process import ShellProcessRunner
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
    config = load_config()

    # Override state path if provided
    if state_path:
        config["state_path"] = state_path

    logger.debug(f"Using state path: {config['state_path']}")

    # Create dependencies
    clock = SystemClock()
    process_runner = ShellProcessRunner()
    function_loader = PythonFunctionLoader()
    run_repo = SQLiteRunRepository(config["state_path"])
    node_repo = SQLiteNodeExecutionRepository(config["state_path"])

    # Create engine
    return RunbookEngine(
        clock=clock,
        process_runner=process_runner,
        function_loader=function_loader,
        run_repo=run_repo,
        node_repo=node_repo,
        io_handler=io_handler,
    )


def get_parser() -> RunbookParser:
    """Get a runbook parser instance"""
    return RunbookParser()


def get_error_handler(debug: bool = False) -> ErrorHandler:
    """Get an error handler instance"""
    return ErrorHandler(console, debug)


def handle_error_and_exit(error: Exception, context: str = None, debug: bool = False) -> None:
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
