# tests/test_infrastructure/test_variables.py
"""Tests for variable management functionality."""

import json
import os
import tempfile
import yaml
from unittest.mock import patch

import pytest

from src.playbook.domain.models import VariableDefinition
from src.playbook.infrastructure.variables import (
    VariableManager,
    VariableValidationError,
    TemplateRenderError,
)
from src.playbook.domain.exceptions import ConfigurationError


class TestVariableDefinition:
    """Test VariableDefinition model validation."""

    def test_given_valid_definition_when_creating_then_validates_successfully(self):
        """Test valid variable definition creation."""
        definition = VariableDefinition(
            default="test",
            required=True,
            type="string",
            description="Test variable"
        )
        assert definition.default == "test"
        assert definition.required is True
        assert definition.type == "string"

    def test_given_int_type_with_choices_when_creating_then_validates_choices(self):
        """Test integer type with valid choices."""
        definition = VariableDefinition(
            type="int",
            choices=[1, 2, 3]
        )
        assert definition.choices == [1, 2, 3]

    def test_given_int_type_with_invalid_choices_when_creating_then_raises_error(self):
        """Test integer type with invalid choices raises error."""
        with pytest.raises(ValueError, match="not an integer"):
            VariableDefinition(
                type="int",
                choices=[1, "2", 3]
            )

    def test_given_string_type_with_min_max_when_creating_then_raises_error(self):
        """Test string type with min/max raises error."""
        with pytest.raises(ValueError, match="min/max can only be used with int or float"):
            VariableDefinition(
                type="string",
                min=1
            )


class TestVariableManager:
    """Test VariableManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VariableManager(interactive=False)

    def test_given_simple_template_when_substituting_then_returns_rendered_string(self):
        """Test basic template substitution."""
        template = "Hello {{name}}!"
        variables = {"name": "World"}
        result = self.manager.substitute_in_string(template, variables)
        assert result == "Hello World!"

    def test_given_template_with_default_when_substituting_then_uses_default(self):
        """Test template with default value."""
        template = "Hello {{name|default('Anonymous')}}!"
        variables = {}
        result = self.manager.substitute_in_string(template, variables)
        assert result == "Hello Anonymous!"

    def test_given_template_with_filter_when_substituting_then_applies_filter(self):
        """Test template with Jinja2 filter."""
        template = "Hello {{name|upper}}!"
        variables = {"name": "world"}
        result = self.manager.substitute_in_string(template, variables)
        assert result == "Hello WORLD!"

    def test_given_complex_template_when_substituting_then_handles_conditionals(self):
        """Test template with conditional logic."""
        template = "{% if debug %}Debug: {{message}}{% else %}{{message}}{% endif %}"
        variables = {"debug": True, "message": "Hello"}
        result = self.manager.substitute_in_string(template, variables)
        assert result == "Debug: Hello"

    def test_given_undefined_variable_when_substituting_then_raises_error(self):
        """Test undefined variable raises error."""
        template = "Hello {{undefined_var}}!"
        variables = {}
        with pytest.raises(TemplateRenderError):
            self.manager.substitute_in_string(template, variables)

    def test_given_invalid_template_when_substituting_then_raises_error(self):
        """Test invalid template syntax raises error."""
        template = "Hello {{name"  # Missing closing brace
        variables = {"name": "World"}
        with pytest.raises(TemplateRenderError):
            self.manager.substitute_in_string(template, variables)

    def test_given_dict_with_templates_when_substituting_then_processes_recursively(self):
        """Test recursive substitution in dictionary."""
        data = {
            "title": "Deploy {{app}}",
            "config": {
                "timeout": "{{timeout}}",
                "env": "{{environment}}"
            },
            "steps": ["echo {{message}}", "sleep {{delay}}"]
        }
        variables = {
            "app": "myapp",
            "timeout": "300",
            "environment": "prod",
            "message": "Starting",
            "delay": "5"
        }
        result = self.manager.substitute_in_dict(data, variables)

        assert result["title"] == "Deploy myapp"
        assert result["config"]["timeout"] == "300"
        assert result["config"]["env"] == "prod"
        assert result["steps"][0] == "echo Starting"
        assert result["steps"][1] == "sleep 5"

    def test_given_cli_variables_when_parsing_then_returns_dict(self):
        """Test CLI variable parsing."""
        var_strings = ["ENV=prod", "PORT=8080", "DEBUG=true", "SERVERS=[\"s1\",\"s2\"]"]
        result = self.manager.parse_cli_variables(var_strings)

        assert result["ENV"] == "prod"
        assert result["PORT"] == "8080"  # Strings by default
        assert result["DEBUG"] == "true"
        assert result["SERVERS"] == ["s1", "s2"]  # JSON parsed

    def test_given_invalid_cli_format_when_parsing_then_raises_error(self):
        """Test invalid CLI variable format raises error."""
        var_strings = ["INVALID"]
        with pytest.raises(ConfigurationError, match="Invalid variable format"):
            self.manager.parse_cli_variables(var_strings)

    def test_given_env_variables_when_loading_then_returns_filtered_dict(self):
        """Test environment variable loading."""
        with patch.dict(os.environ, {
            "PLAYBOOK_VAR_ENV": "test",
            "PLAYBOOK_VAR_PORT": "8080",
            "PLAYBOOK_VAR_LIST": '["a", "b"]',
            "OTHER_VAR": "ignored"
        }):
            result = self.manager.load_variables_from_env("PLAYBOOK_VAR_")
            assert result["ENV"] == "test"
            assert result["PORT"] == "8080"
            assert result["LIST"] == ["a", "b"]
            assert "OTHER_VAR" not in result

    def test_given_variables_from_sources_when_merging_then_respects_priority(self):
        """Test variable merging priority: CLI > file > env > defaults."""
        cli_vars = {"var1": "cli", "var2": "cli"}
        file_vars = {"var1": "file", "var2": "file", "var3": "file"}
        env_vars = {"var1": "env", "var2": "env", "var3": "env", "var4": "env"}
        defaults = {"var1": "default", "var2": "default", "var3": "default", "var4": "default", "var5": "default"}

        result = self.manager.merge_variables(cli_vars, file_vars, env_vars, defaults)

        assert result["var1"] == "cli"        # CLI wins
        assert result["var2"] == "cli"        # CLI wins
        assert result["var3"] == "file"       # File wins over env/defaults
        assert result["var4"] == "env"        # Env wins over defaults
        assert result["var5"] == "default"    # Only in defaults

    def test_given_string_variable_when_validating_then_converts_type(self):
        """Test variable type validation and conversion."""
        variables = {"str_var": "hello", "int_var": "42", "float_var": "3.14", "bool_var": "true"}
        definitions = {
            "str_var": VariableDefinition(type="string"),
            "int_var": VariableDefinition(type="int"),
            "float_var": VariableDefinition(type="float"),
            "bool_var": VariableDefinition(type="bool")
        }

        self.manager.validate_variables(variables, definitions)

        assert variables["str_var"] == "hello"
        assert variables["int_var"] == 42
        assert variables["float_var"] == 3.14
        assert variables["bool_var"] is True

    def test_given_invalid_type_when_validating_then_raises_error(self):
        """Test invalid type validation raises error."""
        variables = {"int_var": "not_a_number"}
        definitions = {"int_var": VariableDefinition(type="int")}

        with pytest.raises(VariableValidationError, match="expected int"):
            self.manager.validate_variables(variables, definitions)

    def test_given_choices_constraint_when_validating_then_enforces_choices(self):
        """Test choices constraint validation."""
        variables = {"env": "invalid"}
        definitions = {
            "env": VariableDefinition(type="string", choices=["dev", "staging", "prod"])
        }

        with pytest.raises(VariableValidationError, match="not in allowed choices"):
            self.manager.validate_variables(variables, definitions)

    def test_given_numeric_constraints_when_validating_then_enforces_limits(self):
        """Test numeric min/max constraints."""
        variables = {"port": 80}
        definitions = {
            "port": VariableDefinition(type="int", min=1024, max=65535)
        }

        with pytest.raises(VariableValidationError, match="below minimum"):
            self.manager.validate_variables(variables, definitions)

    def test_given_string_pattern_when_validating_then_enforces_pattern(self):
        """Test string pattern validation."""
        variables = {"email": "invalid-email"}
        definitions = {
            "email": VariableDefinition(
                type="string",
                pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            )
        }

        with pytest.raises(VariableValidationError, match="does not match pattern"):
            self.manager.validate_variables(variables, definitions)

    def test_given_missing_required_when_checking_then_returns_missing_list(self):
        """Test missing required variable detection."""
        provided = {"optional": "value"}
        definitions = {
            "required": VariableDefinition(required=True),
            "optional": VariableDefinition(required=False)
        }

        missing = self.manager.get_missing_required(definitions, provided)
        assert missing == ["required"]

    def test_given_template_string_when_extracting_variables_then_returns_variable_names(self):
        """Test template variable extraction."""
        template = "Deploy {{app}} version {{version}} to {{env|default('staging')}}"
        variables = self.manager.get_template_variables(template)
        assert variables == {"app", "version", "env"}


class TestVariableFileLoading:
    """Test variable file loading functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VariableManager(interactive=False)

    def test_given_toml_file_when_loading_then_returns_variables(self):
        """Test TOML file loading."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
app_name = "myapp"
port = 8080
debug = true
servers = ["s1", "s2"]
""")
            f.flush()

            try:
                result = self.manager.load_variables_from_file(f.name)
                assert result["app_name"] == "myapp"
                assert result["port"] == 8080
                assert result["debug"] is True
                assert result["servers"] == ["s1", "s2"]
            finally:
                os.unlink(f.name)

    def test_given_json_file_when_loading_then_returns_variables(self):
        """Test JSON file loading."""
        data = {"app": "myapp", "port": 8080, "debug": True}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            f.flush()

            try:
                result = self.manager.load_variables_from_file(f.name)
                assert result == data
            finally:
                os.unlink(f.name)

    def test_given_yaml_file_when_loading_then_returns_variables(self):
        """Test YAML file loading."""
        data = {"app": "myapp", "port": 8080, "debug": True}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(data, f)
            f.flush()

            try:
                result = self.manager.load_variables_from_file(f.name)
                assert result == data
            finally:
                os.unlink(f.name)

    def test_given_env_file_when_loading_then_returns_variables(self):
        """Test .env file loading."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
# This is a comment
APP_NAME=myapp
PORT=8080
DEBUG=true
QUOTED_VALUE="hello world"
""")
            f.flush()

            try:
                result = self.manager.load_variables_from_file(f.name)
                assert result["APP_NAME"] == "myapp"
                assert result["PORT"] == "8080"
                assert result["DEBUG"] == "true"
                assert result["QUOTED_VALUE"] == "hello world"
            finally:
                os.unlink(f.name)

    def test_given_nonexistent_file_when_loading_then_raises_error(self):
        """Test loading nonexistent file raises error."""
        with pytest.raises(ConfigurationError, match="Variable file not found"):
            self.manager.load_variables_from_file("/nonexistent/file.toml")

    def test_given_invalid_json_when_loading_then_raises_error(self):
        """Test loading invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json")
            f.flush()

            try:
                with pytest.raises(ConfigurationError, match="Cannot parse variable file"):
                    self.manager.load_variables_from_file(f.name)
            finally:
                os.unlink(f.name)

    def test_given_unknown_extension_when_loading_then_tries_autodetect(self):
        """Test unknown extension falls back to autodetection."""
        data = {"test": "value"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.unknown', delete=False) as f:
            json.dump(data, f)
            f.flush()

            try:
                result = self.manager.load_variables_from_file(f.name)
                assert result == data
            finally:
                os.unlink(f.name)