# src/playbook/infrastructure/plugins/python_plugin.py
"""Built-in utility functions plugin for common workflow operations."""

import logging
import time
from typing import Any, Dict

from ...domain.plugins import (
    Plugin,
    PluginMetadata,
    FunctionSignature,
    ParameterDef,
    ReturnDef,
    PluginExecutionError,
)

logger = logging.getLogger(__name__)


class PythonPlugin(Plugin):
    """Plugin for built-in utility functions.

    This plugin provides built-in utility functions for common workflow operations
    like notifications, delays, and testing. Custom functionality should be
    implemented as separate plugins following the plugin interface.
    """

    def __init__(self) -> None:
        self._initialized = False

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="python",
            version="1.0.0",
            author="Playbook Team",
            description="Built-in utility functions for common workflow operations",
            functions={
                "notify": FunctionSignature(
                    name="notify",
                    description="Send a notification with the given message",
                    parameters={
                        "message": ParameterDef(
                            type="str", required=True, description="The message to send"
                        )
                    },
                    returns=ReturnDef(type="str", description="Confirmation message"),
                    examples=[
                        {
                            "message": "Deployment completed successfully",
                            "expected_result": "Notification sent: Deployment completed successfully",
                        }
                    ],
                ),
                "sleep": FunctionSignature(
                    name="sleep",
                    description="Pause execution for the specified number of seconds",
                    parameters={
                        "seconds": ParameterDef(
                            type="int",
                            required=True,
                            description="Number of seconds to sleep",
                            min_value=0,
                            max_value=3600,
                        )
                    },
                    returns=ReturnDef(type="str", description="Completion message"),
                    examples=[{"seconds": 5, "expected_result": "done"}],
                ),
                "throw": FunctionSignature(
                    name="throw",
                    description="Intentionally throw an exception (for testing error handling)",
                    parameters={},
                    returns=ReturnDef(
                        type="str",
                        description="Never returns - always raises exception",
                    ),
                    examples=[
                        {"expected_error": "Intentional exception for testing purposes"}
                    ],
                ),
            },
            homepage="https://github.com/sysid/playbook",
            documentation="Built-in utility functions plugin providing common workflow operations",
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin."""
        # Python plugin doesn't need configuration
        self._initialized = True
        logger.debug("PythonPlugin initialized")

    def execute(self, function_name: str, params: Dict[str, Any]) -> Any:
        """Execute a Python function.

        Args:
            function_name: Function to execute ("notify", "sleep", "throw")
            params: Function parameters

        Returns:
            Function result

        Raises:
            PluginExecutionError: If execution fails
        """
        if not self._initialized:
            raise PluginExecutionError("Plugin not initialized")

        # Validate parameters using the parent class method
        self.validate_function_params(function_name, params)

        try:
            if function_name == "notify":
                return self._notify(params["message"])
            elif function_name == "sleep":
                return self._sleep(params["seconds"])
            elif function_name == "throw":
                return self._throw()
            else:
                raise PluginExecutionError(f"Unknown function: {function_name}")
        except Exception as e:
            if isinstance(e, PluginExecutionError):
                raise
            raise PluginExecutionError(
                f"Failed to execute function {function_name}: {e}"
            )

    def _notify(self, message: str) -> str:
        """Send a notification with the given message.

        Args:
            message: The message to send

        Returns:
            Confirmation message
        """
        logger.debug(f"NOTIFICATION: {message}")
        return f"Notification sent: {message}"

    def _sleep(self, seconds: int) -> str:
        """Pause execution for the specified number of seconds.

        Args:
            seconds: Number of seconds to sleep

        Returns:
            Completion message
        """
        time.sleep(seconds)
        return "done"

    def _throw(self) -> str:
        """Intentionally throw an exception for testing purposes.

        Returns:
            Never returns - always raises exception

        Raises:
            Exception: Always raised
        """
        raise Exception("Intentional exception for testing purposes")

    def cleanup(self) -> None:
        """Clean up plugin resources."""
        # Python plugin doesn't have resources to clean up
        logger.debug("PythonPlugin cleaned up")
