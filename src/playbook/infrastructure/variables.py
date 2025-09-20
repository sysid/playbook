# src/playbook/infrastructure/variables.py
"""Variable support for playbook workflows using Jinja2 templating."""

import json
import os
import re
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml
from jinja2 import meta, TemplateError, UndefinedError, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from rich.prompt import Prompt

from ..domain.exceptions import ValidationError, ConfigurationError
from ..domain.models import VariableDefinition


class VariableValidationError(ValidationError):
    """Error raised when variable validation fails."""
    pass


class TemplateRenderError(ValidationError):
    """Error raised when template rendering fails."""
    pass


class VariableManager:
    """Manages variable loading, validation, and Jinja2 template rendering."""

    def __init__(self, interactive: bool = True):
        """Initialize variable manager.

        Args:
            interactive: Whether to prompt for missing required variables
        """
        self.interactive = interactive
        # Use sandboxed environment for security
        self.jinja_env = SandboxedEnvironment(
            # Keep Jinja2 syntax simple and clear
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}',
            # Enable loop controls and other useful features
            extensions=['jinja2.ext.loopcontrols'],
            # Strict undefined variables
            undefined=StrictUndefined
        )

        # Add useful filters
        self.jinja_env.filters.update({
            'env': self._env_filter,
        })

    @staticmethod
    def _env_filter(var_name: str, default: str = '') -> str:
        """Jinja2 filter to get environment variables."""
        return os.getenv(var_name, default)

    @staticmethod
    def load_variables_from_file(file_path: str) -> Dict[str, Any]:
        """Load variables from various file formats.

        Args:
            file_path: Path to variable file

        Returns:
            Dictionary of variables

        Raises:
            ConfigurationError: If file cannot be loaded or parsed
        """
        path = Path(file_path)

        if not path.exists():
            raise ConfigurationError(
                f"Variable file not found: {file_path}",
                suggestion="Check the file path and ensure the file exists"
            )

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Detect format by extension
            suffix = path.suffix.lower()

            if suffix == '.toml':
                # Use tomllib for TOML files
                with open(path, 'rb') as f:
                    return tomllib.load(f)

            elif suffix == '.json':
                return json.loads(content)

            elif suffix in ['.yaml', '.yml']:
                return yaml.safe_load(content) or {}

            elif suffix == '.env':
                # Parse .env format: KEY=value
                variables = {}
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        variables[key.strip()] = value.strip().strip('"\'')
                return variables

            else:
                # Try to auto-detect format
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    try:
                        return yaml.safe_load(content) or {}
                    except yaml.YAMLError:
                        raise ConfigurationError(
                            f"Unknown file format for {file_path}",
                            suggestion="Use .toml, .json, .yaml, or .env extension"
                        )

        except (OSError, PermissionError) as e:
            raise ConfigurationError(
                f"Cannot read variable file {file_path}: {e}",
                suggestion="Check file permissions and disk space"
            )
        except (json.JSONDecodeError, yaml.YAMLError, tomllib.TOMLDecodeError) as e:
            raise ConfigurationError(
                f"Cannot parse variable file {file_path}: {e}",
                suggestion="Check file syntax and format"
            )

    def load_variables_from_env(self, prefix: str = "PLAYBOOK_VAR_") -> Dict[str, Any]:
        """Load variables from environment variables with prefix.

        Args:
            prefix: Environment variable prefix

        Returns:
            Dictionary of variables
        """
        variables = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                var_name = key[len(prefix):]
                # Try to parse as JSON for complex types (arrays, objects), fall back to string
                if value.startswith(('[', '{')):
                    try:
                        variables[var_name] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        variables[var_name] = value
                else:
                    variables[var_name] = value
        return variables

    def parse_cli_variables(self, var_strings: List[str]) -> Dict[str, Any]:
        """Parse CLI variable strings in KEY=VALUE format.

        Args:
            var_strings: List of "KEY=VALUE" strings

        Returns:
            Dictionary of parsed variables

        Raises:
            ConfigurationError: If variable format is invalid
        """
        variables = {}
        for var_string in var_strings:
            if '=' not in var_string:
                raise ConfigurationError(
                    f"Invalid variable format: {var_string}",
                    suggestion="Use KEY=VALUE format, e.g., --var ENVIRONMENT=production"
                )

            key, value = var_string.split('=', 1)
            key = key.strip()
            value = value.strip()

            # Try to parse as JSON for complex types (arrays, objects), fall back to string
            if value.startswith(('[', '{')):
                try:
                    variables[key] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    variables[key] = value
            else:
                variables[key] = value

        return variables

    def merge_variables(
        self,
        cli_vars: Optional[Dict[str, Any]] = None,
        file_vars: Optional[Dict[str, Any]] = None,
        env_vars: Optional[Dict[str, Any]] = None,
        defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Merge variables from different sources with priority order.

        Priority: CLI > file > environment > defaults

        Args:
            cli_vars: Variables from CLI arguments
            file_vars: Variables from files
            env_vars: Variables from environment
            defaults: Default values from variable definitions

        Returns:
            Merged dictionary of variables
        """
        merged = {}

        # Apply in reverse priority order
        for source in [defaults, env_vars, file_vars, cli_vars]:
            if source:
                merged.update(source)

        return merged

    def validate_variables(
        self,
        variables: Dict[str, Any],
        definitions: Dict[str, VariableDefinition]
    ) -> None:
        """Validate variables against their definitions.

        Args:
            variables: Variable values to validate
            definitions: Variable definitions

        Raises:
            VariableValidationError: If validation fails
        """
        errors = []

        # Check required variables
        for name, definition in definitions.items():
            if definition.required and name not in variables:
                errors.append(f"Required variable '{name}' is missing")
                continue

            if name not in variables:
                continue  # Skip validation for optional missing variables

            value = variables[name]

            # Type validation
            try:
                validated_value = self._validate_variable_type(value, definition)
                variables[name] = validated_value  # Update with converted value
            except ValueError as e:
                errors.append(f"Variable '{name}': {e}")
                continue

            # Additional validations
            try:
                self._validate_variable_constraints(name, validated_value, definition)
            except ValueError as e:
                errors.append(str(e))

        if errors:
            raise VariableValidationError(
                f"Variable validation failed: {'; '.join(errors)}",
                suggestion="Check variable types and constraints in your workflow definition"
            )

    @staticmethod
    def _validate_variable_type(value: Any, definition: VariableDefinition) -> Any:
        """Validate and convert variable type."""
        expected_type = definition.type

        if expected_type == 'string':
            return str(value)
        elif expected_type == 'int':
            if isinstance(value, bool):  # bool is subclass of int in Python
                raise ValueError("expected int, got bool")
            try:
                return int(value)
            except (ValueError, TypeError):
                raise ValueError(f"expected int, got {type(value).__name__}")
        elif expected_type == 'float':
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ValueError(f"expected float, got {type(value).__name__}")
        elif expected_type == 'bool':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ('true', '1', 'yes', 'on'):
                    return True
                elif value.lower() in ('false', '0', 'no', 'off'):
                    return False
            raise ValueError(f"expected bool, got {type(value).__name__}")
        elif expected_type == 'list':
            if not isinstance(value, list):
                raise ValueError(f"expected list, got {type(value).__name__}")
            return value
        else:
            raise ValueError(f"unknown type: {expected_type}")

    @staticmethod
    def _validate_variable_constraints(
        name: str,
        value: Any,
        definition: VariableDefinition
    ) -> None:
        """Validate variable against constraints."""
        # Choices validation
        if definition.choices and value not in definition.choices:
            choices_str = ', '.join(str(c) for c in definition.choices)
            raise ValueError(
                f"Variable '{name}' value '{value}' not in allowed choices: [{choices_str}]"
            )

        # Numeric constraints
        if definition.type in ['int', 'float']:
            if definition.min is not None and value < definition.min:
                raise ValueError(
                    f"Variable '{name}' value {value} is below minimum {definition.min}"
                )
            if definition.max is not None and value > definition.max:
                raise ValueError(
                    f"Variable '{name}' value {value} is above maximum {definition.max}"
                )

        # String pattern validation
        if definition.type == 'string' and definition.pattern:
            if not re.match(definition.pattern, str(value)):
                raise ValueError(
                    f"Variable '{name}' value '{value}' does not match pattern '{definition.pattern}'"
                )

    @staticmethod
    def get_missing_required(
        definitions: Dict[str, VariableDefinition],
        provided: Dict[str, Any]
    ) -> List[str]:
        """Get list of missing required variables.

        Args:
            definitions: Variable definitions
            provided: Provided variable values

        Returns:
            List of missing required variable names
        """
        missing = []
        for name, definition in definitions.items():
            if definition.required and name not in provided:
                missing.append(name)
        return missing

    def prompt_for_missing_variables(
        self,
        missing: List[str],
        definitions: Dict[str, VariableDefinition]
    ) -> Dict[str, Any]:
        """Interactively prompt for missing required variables.

        Args:
            missing: List of missing variable names
            definitions: Variable definitions

        Returns:
            Dictionary of prompted variables
        """
        if not self.interactive:
            return {}

        prompted = {}
        for name in missing:
            definition = definitions[name]

            # Build prompt message
            prompt_msg = f"Enter value for {name}"
            if definition.description:
                prompt_msg += f" ({definition.description})"
            if definition.choices:
                choices_str = ', '.join(str(c) for c in definition.choices)
                prompt_msg += f" [choices: {choices_str}]"

            # Get value with validation
            while True:
                try:
                    value = Prompt.ask(prompt_msg)
                    validated_value = self._validate_variable_type(value, definition)
                    self._validate_variable_constraints(name, validated_value, definition)
                    prompted[name] = validated_value
                    break
                except ValueError as e:
                    print(f"Invalid value: {e}. Please try again.")

        return prompted

    def substitute_in_string(self, template_str: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in a string using Jinja2.

        Args:
            template_str: String with Jinja2 template syntax
            variables: Variables to substitute

        Returns:
            Rendered string

        Raises:
            TemplateRenderError: If template rendering fails
        """
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**variables)
        except (TemplateError, UndefinedError) as e:
            raise TemplateRenderError(
                f"Template rendering failed: {e}",
                context={"template": template_str, "variables": list(variables.keys())},
                suggestion="Check template syntax and ensure all variables are defined"
            )

    def substitute_in_dict(self, data: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively substitute variables in dictionary values.

        Args:
            data: Dictionary to process
            variables: Variables to substitute

        Returns:
            Dictionary with substituted values
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.substitute_in_string(value, variables)
            elif isinstance(value, dict):
                result[key] = self.substitute_in_dict(value, variables)
            elif isinstance(value, list):
                result[key] = self._substitute_in_list(value, variables)
            else:
                result[key] = value
        return result

    def _substitute_in_list(self, data: List[Any], variables: Dict[str, Any]) -> List[Any]:
        """Recursively substitute variables in list values."""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(self.substitute_in_string(item, variables))
            elif isinstance(item, dict):
                result.append(self.substitute_in_dict(item, variables))
            elif isinstance(item, list):
                result.append(self._substitute_in_list(item, variables))
            else:
                result.append(item)
        return result

    def get_template_variables(self, template_str: str) -> set[str]:
        """Extract variable names used in a Jinja2 template.

        Args:
            template_str: Template string

        Returns:
            Set of variable names found in template
        """
        try:
            parsed = self.jinja_env.parse(template_str)
            return meta.find_undeclared_variables(parsed)
        except TemplateError:
            # If parsing fails, return empty set
            return set()
