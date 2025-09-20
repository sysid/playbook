# tests/test_domain/test_plugin_type_conversion.py
"""Tests for plugin parameter type conversion functionality."""

import pytest
from unittest.mock import Mock

from src.playbook.domain.plugins import (
    Plugin,
    PluginMetadata,
    FunctionSignature,
    ParameterDef,
)


class MockPlugin(Plugin):
    """Mock plugin for testing type conversion."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test",
            version="1.0.0",
            author="Test",
            description="Test plugin for type conversion",
            functions={
                "test_types": FunctionSignature(
                    name="test_types",
                    description="Test function with various parameter types",
                    parameters={
                        "str_param": ParameterDef(type="str", required=True),
                        "int_param": ParameterDef(type="int", required=True),
                        "float_param": ParameterDef(type="float", required=True),
                        "bool_param": ParameterDef(type="bool", required=True),
                        "list_param": ParameterDef(type="list", required=False),
                        "dict_param": ParameterDef(type="dict", required=False),
                    },
                )
            },
        )

    def initialize(self, config):
        pass

    def execute(self, function_name, params):
        return "executed"

    def cleanup(self):
        pass


class TestPluginTypeConversion:
    """Test parameter type conversion in plugins."""

    @pytest.fixture
    def plugin(self):
        """Create a mock plugin instance."""
        return MockPlugin()

    def test_string_parameter_no_conversion(self, plugin):
        """Test string parameters don't get converted."""
        params = {
            "str_param": "hello",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
        }
        plugin.validate_function_params("test_types", params)

        assert params["str_param"] == "hello"  # Remains string
        assert params["int_param"] == 42  # Converted to int
        assert params["float_param"] == 3.14  # Converted to float
        assert params["bool_param"] is True  # Converted to bool

    def test_integer_conversion_from_string(self, plugin):
        """Test integer conversion from string values."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
        }
        plugin.validate_function_params("test_types", params)

        assert params["int_param"] == 42
        assert isinstance(params["int_param"], int)

    def test_float_conversion_from_string(self, plugin):
        """Test float conversion from string values."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
        }
        plugin.validate_function_params("test_types", params)

        assert params["float_param"] == 3.14
        assert isinstance(params["float_param"], float)

    def test_boolean_conversion_from_string(self, plugin):
        """Test boolean conversion from various string representations."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for input_value, expected in test_cases:
            params = {
                "str_param": "test",
                "int_param": "42",
                "float_param": "3.14",
                "bool_param": input_value,
            }
            plugin.validate_function_params("test_types", params)
            assert params["bool_param"] is expected, f"Failed for input: {input_value}"

    def test_list_conversion_from_json_string(self, plugin):
        """Test list conversion from JSON string."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
            "list_param": '["a", "b", 123]',
        }
        plugin.validate_function_params("test_types", params)

        assert params["list_param"] == ["a", "b", 123]
        assert isinstance(params["list_param"], list)

    def test_dict_conversion_from_json_string(self, plugin):
        """Test dict conversion from JSON string."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
            "dict_param": '{"key": "value", "number": 42}',
        }
        plugin.validate_function_params("test_types", params)

        assert params["dict_param"] == {"key": "value", "number": 42}
        assert isinstance(params["dict_param"], dict)

    def test_already_correct_types_no_conversion(self, plugin):
        """Test that already correctly typed values don't get converted."""
        params = {
            "str_param": "test",
            "int_param": 42,
            "float_param": 3.14,
            "bool_param": True,
            "list_param": ["a", "b"],
            "dict_param": {"key": "value"},
        }
        original_params = params.copy()
        plugin.validate_function_params("test_types", params)

        # Values should remain unchanged
        assert params == original_params

    def test_invalid_integer_conversion_fails(self, plugin):
        """Test that invalid integer conversion raises ValueError."""
        params = {
            "str_param": "test",
            "int_param": "not_a_number",
            "float_param": "3.14",
            "bool_param": "true",
        }

        with pytest.raises(ValueError, match="Cannot convert parameter 'int_param'"):
            plugin.validate_function_params("test_types", params)

    def test_invalid_float_conversion_fails(self, plugin):
        """Test that invalid float conversion raises ValueError."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "not_a_number",
            "bool_param": "true",
        }

        with pytest.raises(ValueError, match="Cannot convert parameter 'float_param'"):
            plugin.validate_function_params("test_types", params)

    def test_invalid_boolean_conversion_fails(self, plugin):
        """Test that invalid boolean conversion raises ValueError."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "maybe",
        }

        with pytest.raises(ValueError, match="Cannot convert parameter 'bool_param'"):
            plugin.validate_function_params("test_types", params)

    def test_invalid_json_conversion_fails(self, plugin):
        """Test that invalid JSON conversion raises ValueError."""
        params = {
            "str_param": "test",
            "int_param": "42",
            "float_param": "3.14",
            "bool_param": "true",
            "list_param": "not_valid_json",
        }

        with pytest.raises(ValueError, match="Cannot convert parameter 'list_param'"):
            plugin.validate_function_params("test_types", params)

    def test_unsupported_type_conversion_fails(self, plugin):
        """Test that unsupported type conversions fail gracefully."""
        # Test with a non-string, non-target type
        params = {
            "str_param": "test",
            "int_param": [],
            "float_param": "3.14",
            "bool_param": "true",
        }

        with pytest.raises(ValueError, match="Cannot convert parameter 'int_param'"):
            plugin.validate_function_params("test_types", params)

    def test_jinja2_template_simulation(self, plugin):
        """Test simulation of Jinja2 template variable substitution."""
        # This simulates what happens when Jinja2 substitutes {{SLEEP_DURATION}} with "2"
        params = {
            "str_param": "demo-app",  # {{APP_NAME}}
            "int_param": "2",  # {{SLEEP_DURATION}}
            "float_param": "1.5",  # {{TIMEOUT}}
            "bool_param": "true",  # {{ENABLED}}
        }

        plugin.validate_function_params("test_types", params)

        # All should be properly converted
        assert params["str_param"] == "demo-app"
        assert params["int_param"] == 2
        assert params["float_param"] == 1.5
        assert params["bool_param"] is True
