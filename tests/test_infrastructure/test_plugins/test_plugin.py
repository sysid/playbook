# tests/test_infrastructure/test_plugins/test_plugin.py
"""Test plugin for testing plugin system functionality."""

from typing import Any, Dict

from src.playbook.domain.plugins import (
    Plugin,
    PluginMetadata,
    FunctionSignature,
    ParameterDef,
    ReturnDef,
    PluginExecutionError
)


class ExampleTestPlugin(Plugin):
    """Simple test plugin for unit testing."""

    def __init__(self):
        self._config = {}
        self._initialized = False

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test",
            version="1.0.0",
            author="Test Author",
            description="A simple test plugin",
            functions={
                "echo": FunctionSignature(
                    name="echo",
                    description="Echo back the input message",
                    parameters={
                        "message": ParameterDef(
                            type="str",
                            required=True,
                            description="Message to echo back"
                        )
                    },
                    returns=ReturnDef(
                        type="str",
                        description="The echoed message"
                    )
                ),
                "add": FunctionSignature(
                    name="add",
                    description="Add two numbers",
                    parameters={
                        "a": ParameterDef(
                            type="int",
                            required=True,
                            description="First number"
                        ),
                        "b": ParameterDef(
                            type="int",
                            required=True,
                            description="Second number"
                        )
                    },
                    returns=ReturnDef(
                        type="int",
                        description="Sum of a and b"
                    )
                ),
                "error": FunctionSignature(
                    name="error",
                    description="Function that always fails",
                    parameters={},
                    returns=ReturnDef(
                        type="str",
                        description="Never returns"
                    )
                )
            }
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config.copy()
        self._initialized = True

    def execute(self, function_name: str, params: Dict[str, Any]) -> Any:
        if not self._initialized:
            raise PluginExecutionError("Plugin not initialized")

        # Validate parameters
        self.validate_function_params(function_name, params)

        if function_name == "echo":
            return f"Echo: {params['message']}"
        elif function_name == "add":
            return params["a"] + params["b"]
        elif function_name == "error":
            raise PluginExecutionError("Test error from plugin")
        else:
            raise ValueError(f"Unknown function: {function_name}")

    def cleanup(self) -> None:
        self._config = {}
        self._initialized = False


class ConfigurableTestPlugin(Plugin):
    """Test plugin that uses configuration."""

    def __init__(self):
        self._prefix = ""
        self._initialized = False

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="configurable_test",
            version="1.0.0",
            author="Test Author",
            description="A configurable test plugin",
            functions={
                "greet": FunctionSignature(
                    name="greet",
                    description="Greet a person with configured prefix",
                    parameters={
                        "name": ParameterDef(
                            type="str",
                            required=True,
                            description="Name to greet"
                        )
                    },
                    returns=ReturnDef(
                        type="str",
                        description="Greeting message"
                    )
                )
            }
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        self._prefix = config.get("prefix", "Hello")
        self._initialized = True

    def execute(self, function_name: str, params: Dict[str, Any]) -> Any:
        if not self._initialized:
            raise PluginExecutionError("Plugin not initialized")

        self.validate_function_params(function_name, params)

        if function_name == "greet":
            return f"{self._prefix}, {params['name']}!"
        else:
            raise ValueError(f"Unknown function: {function_name}")

    def cleanup(self) -> None:
        self._prefix = ""
        self._initialized = False