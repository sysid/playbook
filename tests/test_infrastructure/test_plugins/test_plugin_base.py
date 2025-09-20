# tests/test_infrastructure/test_plugins/test_plugin_base.py
"""Tests for plugin base classes and validation."""

import pytest

from src.playbook.domain.plugins import (
    ParameterDef,
    FunctionSignature,
    PluginMetadata,
    Plugin
)
from tests.test_infrastructure.test_plugins.test_plugin import ExampleTestPlugin


class TestPluginBaseClasses:
    """Test the plugin base classes and validation."""

    def test_parameter_def_creation(self):
        """Test creating parameter definitions."""
        param = ParameterDef(
            type="str",
            required=True,
            description="Test parameter",
            choices=["a", "b", "c"]
        )

        assert param.type == "str"
        assert param.required is True
        assert param.description == "Test parameter"
        assert param.choices == ["a", "b", "c"]

    def test_parameter_def_defaults(self):
        """Test parameter definition defaults."""
        param = ParameterDef()

        assert param.type == "str"
        assert param.required is True
        assert param.description is None
        assert param.default is None

    def test_function_signature_creation(self):
        """Test creating function signatures."""
        sig = FunctionSignature(
            name="test_func",
            description="Test function",
            parameters={
                "param1": ParameterDef(type="str", required=True),
                "param2": ParameterDef(type="int", required=False, default=42)
            }
        )

        assert sig.name == "test_func"
        assert sig.description == "Test function"
        assert len(sig.parameters) == 2
        assert "param1" in sig.parameters
        assert "param2" in sig.parameters

    def test_plugin_metadata_creation(self):
        """Test creating plugin metadata."""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            author="Test Author",
            description="Test plugin",
            functions={
                "func1": FunctionSignature(
                    name="func1",
                    description="Function 1"
                )
            }
        )

        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert "func1" in metadata.functions

    def test_plugin_parameter_validation_success(self):
        """Test successful parameter validation."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        # Should not raise any exception
        plugin.validate_function_params("echo", {"message": "hello"})

    def test_plugin_parameter_validation_missing_required(self):
        """Test validation of missing required parameters."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        with pytest.raises(ValueError, match="Required parameter 'message' missing"):
            plugin.validate_function_params("echo", {})

    def test_plugin_parameter_validation_unknown_param(self):
        """Test validation of unknown parameters."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        with pytest.raises(ValueError, match="Unknown parameter 'unknown'"):
            plugin.validate_function_params("echo", {"message": "hello", "unknown": "value"})

    def test_plugin_parameter_validation_type_checking(self):
        """Test parameter type validation."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        # String parameter with integer value
        with pytest.raises(ValueError, match="Cannot convert parameter 'message' value '123' \\(type: int\\) to str"):
            plugin.validate_function_params("echo", {"message": 123})

        # Integer parameter with string value
        with pytest.raises(ValueError, match="Cannot convert parameter 'a' value 'not_a_number' to int"):
            plugin.validate_function_params("add", {"a": "not_a_number", "b": 2})

    def test_plugin_parameter_validation_unknown_function(self):
        """Test validation with unknown function."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        with pytest.raises(ValueError, match="Function 'unknown_func' not found"):
            plugin.validate_function_params("unknown_func", {})

    def test_plugin_parameter_validation_choices(self):
        """Test parameter validation with choices."""
        # Create a plugin with choice-constrained parameter
        class ChoiceTestPlugin(Plugin):
            def get_metadata(self):
                return PluginMetadata(
                    name="choice_test",
                    version="1.0.0",
                    author="test",
                    description="test",
                    functions={
                        "choose": FunctionSignature(
                            name="choose",
                            description="Choose from options",
                            parameters={
                                "option": ParameterDef(
                                    type="str",
                                    required=True,
                                    choices=["A", "B", "C"]
                                )
                            }
                        )
                    }
                )

            def initialize(self, config):
                pass

            def execute(self, function_name, params):
                return params["option"]

            def cleanup(self):
                pass

        plugin = ChoiceTestPlugin()

        # Valid choice
        plugin.validate_function_params("choose", {"option": "A"})

        # Invalid choice
        with pytest.raises(ValueError, match="Parameter 'option' must be one of \\['A', 'B', 'C'\\]"):
            plugin.validate_function_params("choose", {"option": "D"})

    def test_plugin_parameter_validation_numeric_range(self):
        """Test parameter validation with numeric ranges."""
        class RangeTestPlugin(Plugin):
            def get_metadata(self):
                return PluginMetadata(
                    name="range_test",
                    version="1.0.0",
                    author="test",
                    description="test",
                    functions={
                        "range_func": FunctionSignature(
                            name="range_func",
                            description="Function with range validation",
                            parameters={
                                "value": ParameterDef(
                                    type="int",
                                    required=True,
                                    min_value=1,
                                    max_value=100
                                )
                            }
                        )
                    }
                )

            def initialize(self, config):
                pass

            def execute(self, function_name, params):
                return params["value"]

            def cleanup(self):
                pass

        plugin = RangeTestPlugin()

        # Valid range
        plugin.validate_function_params("range_func", {"value": 50})

        # Below minimum
        with pytest.raises(ValueError, match="Parameter 'value' must be >= 1"):
            plugin.validate_function_params("range_func", {"value": 0})

        # Above maximum
        with pytest.raises(ValueError, match="Parameter 'value' must be <= 100"):
            plugin.validate_function_params("range_func", {"value": 101})

    def test_plugin_parameter_validation_pattern(self):
        """Test parameter validation with regex patterns."""
        class PatternTestPlugin(Plugin):
            def get_metadata(self):
                return PluginMetadata(
                    name="pattern_test",
                    version="1.0.0",
                    author="test",
                    description="test",
                    functions={
                        "email": FunctionSignature(
                            name="email",
                            description="Validate email format",
                            parameters={
                                "email": ParameterDef(
                                    type="str",
                                    required=True,
                                    pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                                )
                            }
                        )
                    }
                )

            def initialize(self, config):
                pass

            def execute(self, function_name, params):
                return params["email"]

            def cleanup(self):
                pass

        plugin = PatternTestPlugin()

        # Valid email
        plugin.validate_function_params("email", {"email": "test@example.com"})

        # Invalid email
        with pytest.raises(ValueError, match="Parameter 'email' does not match required pattern"):
            plugin.validate_function_params("email", {"email": "invalid-email"})


class TestPluginExecution:
    """Test plugin execution functionality."""

    def test_plugin_execution_success(self):
        """Test successful plugin function execution."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        result = plugin.execute("echo", {"message": "hello world"})

        assert result == "Echo: hello world"

    def test_plugin_execution_math(self):
        """Test plugin math function execution."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        result = plugin.execute("add", {"a": 5, "b": 3})

        assert result == 8

    def test_plugin_execution_error(self):
        """Test plugin function that raises an error."""
        plugin = ExampleTestPlugin()
        plugin.initialize({})

        with pytest.raises(Exception, match="Test error from plugin"):
            plugin.execute("error", {})

    def test_plugin_execution_uninitialized(self):
        """Test executing function on uninitialized plugin."""
        plugin = ExampleTestPlugin()

        with pytest.raises(Exception, match="Plugin not initialized"):
            plugin.execute("echo", {"message": "hello"})