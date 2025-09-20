# src/playbook/domain/plugins.py
"""Plugin system interfaces and models for Playbook."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ParameterDef(BaseModel):
    """Definition of a function parameter."""
    type: str = "str"  # str, int, float, bool, list, dict
    required: bool = True
    description: Optional[str] = None
    default: Optional[Any] = None
    choices: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None  # For string validation

    model_config = {"extra": "forbid"}


class ReturnDef(BaseModel):
    """Definition of function return value."""
    type: str = "str"  # str, int, float, bool, list, dict
    description: Optional[str] = None

    model_config = {"extra": "forbid"}


class FunctionSignature(BaseModel):
    """Signature definition for a plugin function."""
    name: str
    description: str
    parameters: Dict[str, ParameterDef] = Field(default_factory=dict)
    returns: ReturnDef = Field(default_factory=lambda: ReturnDef())
    timeout: Optional[int] = None  # Override default timeout
    requires_auth: bool = False
    examples: Optional[List[Dict[str, Any]]] = None

    model_config = {"extra": "forbid"}


class PluginMetadata(BaseModel):
    """Metadata for a plugin."""
    name: str
    version: str
    author: str
    description: str
    functions: Dict[str, FunctionSignature] = Field(default_factory=dict)
    requires: List[str] = Field(default_factory=list)  # Plugin dependencies
    config_schema: Optional[Dict[str, Any]] = None
    homepage: Optional[str] = None
    documentation: Optional[str] = None

    model_config = {"extra": "forbid"}


class PluginExecutionResult(BaseModel):
    """Result of plugin function execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    output: Optional[str] = None  # For console output/logs

    model_config = {"extra": "forbid"}


class Plugin(ABC):
    """Abstract base class for all plugins."""

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata including available functions."""
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration dictionary

        Raises:
            PluginInitializationError: If initialization fails
        """
        pass

    @abstractmethod
    def execute(self, function_name: str, params: Dict[str, Any]) -> Any:
        """Execute a specific function within the plugin.

        Args:
            function_name: Name of the function to execute
            params: Function parameters

        Returns:
            Function result

        Raises:
            PluginExecutionError: If execution fails
            ValueError: If function not found or invalid parameters
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up plugin resources."""
        pass

    def validate_function_params(self, function_name: str, params: Dict[str, Any]) -> None:
        """Validate function parameters against signature with automatic type conversion.

        Args:
            function_name: Name of the function
            params: Parameters to validate and convert

        Raises:
            ValueError: If validation fails
        """
        metadata = self.get_metadata()
        if function_name not in metadata.functions:
            raise ValueError(f"Function '{function_name}' not found in plugin '{metadata.name}'")

        func_sig = metadata.functions[function_name]

        # Check required parameters
        for param_name, param_def in func_sig.parameters.items():
            if param_def.required and param_name not in params:
                raise ValueError(f"Required parameter '{param_name}' missing for function '{function_name}'")

        # Convert and validate parameter types
        for param_name, value in params.items():
            if param_name not in func_sig.parameters:
                raise ValueError(f"Unknown parameter '{param_name}' for function '{function_name}'")

            param_def = func_sig.parameters[param_name]
            # Convert parameter value if needed (modifies params in-place)
            converted_value = self._convert_parameter_value(param_name, value, param_def)
            params[param_name] = converted_value
            # Validate the converted value
            self._validate_parameter_value(param_name, converted_value, param_def)

    def _convert_parameter_value(self, param_name: str, value: Any, param_def: ParameterDef) -> Any:
        """Convert parameter value to the expected type.

        Handles automatic conversion from string values (common with Jinja2 templates)
        to the expected parameter type.

        Args:
            param_name: Name of the parameter
            value: Value to convert
            param_def: Parameter definition with type information

        Returns:
            Converted value

        Raises:
            ValueError: If conversion fails
        """
        expected_type = param_def.type.lower()

        # If value is already the correct type, return as-is
        if expected_type == "str" and isinstance(value, str):
            return value
        elif expected_type == "int" and isinstance(value, int):
            return value
        elif expected_type == "float" and isinstance(value, (int, float)):
            return value
        elif expected_type == "bool" and isinstance(value, bool):
            return value
        elif expected_type == "list" and isinstance(value, list):
            return value
        elif expected_type == "dict" and isinstance(value, dict):
            return value

        # If value is a string, attempt conversion to target type
        if isinstance(value, str):
            if expected_type == "int":
                try:
                    return int(value)
                except ValueError:
                    raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' to {expected_type}")
            elif expected_type == "float":
                try:
                    return float(value)
                except ValueError:
                    raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' to {expected_type}")
            elif expected_type == "bool":
                # Handle common boolean string representations
                lower_value = value.lower().strip()
                if lower_value in ("true", "1", "yes", "on"):
                    return True
                elif lower_value in ("false", "0", "no", "off"):
                    return False
                else:
                    raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' to {expected_type}")
            elif expected_type == "list":
                # Attempt JSON parsing for lists
                try:
                    import json
                    return json.loads(value)
                except (ValueError, json.JSONDecodeError):
                    raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' to {expected_type}")
            elif expected_type == "dict":
                # Attempt JSON parsing for dicts
                try:
                    import json
                    return json.loads(value)
                except (ValueError, json.JSONDecodeError):
                    raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' to {expected_type}")
            elif expected_type == "str":
                return value  # Already a string

        # If we get here, the conversion wasn't possible
        raise ValueError(f"Cannot convert parameter '{param_name}' value '{value}' (type: {type(value).__name__}) to {expected_type}")

    def _validate_parameter_value(self, param_name: str, value: Any, param_def: ParameterDef) -> None:
        """Validate a single parameter value."""
        # Type validation
        expected_type = param_def.type.lower()
        if expected_type == "str" and not isinstance(value, str):
            raise ValueError(f"Parameter '{param_name}' must be a string")
        elif expected_type == "int" and not isinstance(value, int):
            raise ValueError(f"Parameter '{param_name}' must be an integer")
        elif expected_type == "float" and not isinstance(value, (int, float)):
            raise ValueError(f"Parameter '{param_name}' must be a number")
        elif expected_type == "bool" and not isinstance(value, bool):
            raise ValueError(f"Parameter '{param_name}' must be a boolean")
        elif expected_type == "list" and not isinstance(value, list):
            raise ValueError(f"Parameter '{param_name}' must be a list")
        elif expected_type == "dict" and not isinstance(value, dict):
            raise ValueError(f"Parameter '{param_name}' must be a dictionary")

        # Choices validation
        if param_def.choices and value not in param_def.choices:
            raise ValueError(f"Parameter '{param_name}' must be one of {param_def.choices}")

        # Numeric range validation
        if expected_type in ("int", "float"):
            if param_def.min_value is not None and value < param_def.min_value:
                raise ValueError(f"Parameter '{param_name}' must be >= {param_def.min_value}")
            if param_def.max_value is not None and value > param_def.max_value:
                raise ValueError(f"Parameter '{param_name}' must be <= {param_def.max_value}")

        # String pattern validation
        if expected_type == "str" and param_def.pattern:
            import re
            if not re.match(param_def.pattern, value):
                raise ValueError(f"Parameter '{param_name}' does not match required pattern")


# Plugin system exceptions
class PluginError(Exception):
    """Base exception for plugin system errors."""
    pass


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found."""
    pass


class PluginInitializationError(PluginError):
    """Raised when plugin initialization fails."""
    pass


class PluginExecutionError(PluginError):
    """Raised when plugin execution fails."""
    pass


class FunctionNotFoundError(PluginError):
    """Raised when a requested function is not found in a plugin."""
    pass