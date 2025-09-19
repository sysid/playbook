# tests/test_infrastructure/test_parser_variables.py
"""Tests for parser integration with variable support."""

import tempfile
from pathlib import Path

import pytest

from src.playbook.infrastructure.parser import RunbookParser
from src.playbook.infrastructure.variables import VariableManager, VariableValidationError


class TestRunbookParserVariables:
    """Test RunbookParser with variable support."""

    def setup_method(self):
        """Set up test fixtures."""
        self.variable_manager = VariableManager(interactive=False)
        self.parser = RunbookParser(variable_manager=self.variable_manager)

    def test_given_runbook_without_variables_when_parsing_then_works_normally(self):
        """Test parsing runbook without variables section."""
        toml_content = """
[runbook]
title = "Test Runbook"
description = "Test runbook"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Manual"
prompt_after = "Ready to start?"
description = "Start the workflow"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                runbook = self.parser.parse(f.name)
                assert runbook.title == "Test Runbook"
                assert "start" in runbook.nodes
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_simple_variables_when_parsing_then_substitutes_values(self):
        """Test parsing runbook with simple variable substitution."""
        toml_content = """
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
VERSION = { default = "1.0.0", description = "Version to deploy" }

[runbook]
title = "Deploy {{APP_NAME}}"
description = "Deploy {{APP_NAME}} version {{VERSION}}"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[deploy]
type = "Command"
command_name = "echo 'Deploying {{APP_NAME}} {{VERSION}}'"
description = "Deploy {{APP_NAME}}"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                variables = {"APP_NAME": "testapp", "VERSION": "2.0.0"}
                runbook = self.parser.parse(f.name, variables=variables)

                assert runbook.title == "Deploy testapp"
                assert runbook.description == "Deploy testapp version 2.0.0"

                deploy_node = runbook.nodes["deploy"]
                assert deploy_node.command_name == "echo 'Deploying testapp 2.0.0'"
                assert deploy_node.description == "Deploy testapp"
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_defaults_when_parsing_without_variables_then_uses_defaults(self):
        """Test parsing uses default values when no variables provided."""
        toml_content = """
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
ENVIRONMENT = { default = "staging", description = "Target environment" }

[runbook]
title = "Deploy to {{ENVIRONMENT}}"
description = "Deploy {{APP_NAME}} to {{ENVIRONMENT}}"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[deploy]
type = "Command"
command_name = "kubectl apply -f {{APP_NAME}}-{{ENVIRONMENT}}.yaml"
description = "Deploy to {{ENVIRONMENT}}"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                runbook = self.parser.parse(f.name)

                assert runbook.title == "Deploy to staging"
                assert runbook.description == "Deploy myapp to staging"

                deploy_node = runbook.nodes["deploy"]
                assert deploy_node.command_name == "kubectl apply -f myapp-staging.yaml"
                assert deploy_node.description == "Deploy to staging"
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_required_variables_when_parsing_without_them_then_raises_error(self):
        """Test parsing with missing required variables raises error."""
        toml_content = """
[variables]
REQUIRED_VAR = { required = true, description = "This is required" }

[runbook]
title = "Test {{REQUIRED_VAR}}"
description = "Test runbook"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Manual"
description = "Start"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                with pytest.raises(VariableValidationError, match="Required variable"):
                    self.parser.parse(f.name)
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_type_validation_when_parsing_then_validates_types(self):
        """Test parsing validates variable types."""
        toml_content = """
[variables]
PORT = { default = 8080, type = "int", description = "Port number" }
DEBUG = { default = false, type = "bool", description = "Debug mode" }

[runbook]
title = "Test Runbook"
description = "Test runbook"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Command"
command_name = "server --port={{PORT}} {% if DEBUG %}--debug{% endif %}"
description = "Start server"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                variables = {"PORT": "9000", "DEBUG": "true"}  # String inputs
                runbook = self.parser.parse(f.name, variables=variables)

                start_node = runbook.nodes["start"]
                assert start_node.command_name == "server --port=9000 --debug"
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_choices_when_parsing_with_invalid_choice_then_raises_error(self):
        """Test parsing with invalid choice raises error."""
        toml_content = """
[variables]
ENVIRONMENT = { choices = ["dev", "staging", "prod"], description = "Environment" }

[runbook]
title = "Deploy to {{ENVIRONMENT}}"
description = "Test runbook"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Manual"
description = "Start"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                variables = {"ENVIRONMENT": "invalid"}
                with pytest.raises(VariableValidationError, match="not in allowed choices"):
                    self.parser.parse(f.name, variables=variables)
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_complex_jinja_when_parsing_then_handles_advanced_features(self):
        """Test parsing with complex Jinja2 features within TOML values."""
        toml_content = """
[variables]
SERVICES = { default = ["api", "web"], type = "list", description = "Services to deploy" }
ENVIRONMENT = { default = "staging", description = "Environment" }
SKIP_TESTS = { default = false, type = "bool", description = "Skip tests" }

[runbook]
title = "Deploy Services"
description = "Deploy multiple services"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[deploy_all]
type = "Command"
command_name = "{% for service in SERVICES %}deploy {{service}} --env={{ENVIRONMENT}} && {% endfor %}echo 'All services deployed'"
description = "Deploy all services: {{ SERVICES | join(', ') }}"
skip = "{{SKIP_TESTS}}"
depends_on = []

[conditional_test]
type = "Command"
command_name = "{% if not SKIP_TESTS %}run-tests --env={{ENVIRONMENT}}{% else %}echo 'Tests skipped'{% endif %}"
description = "{% if not SKIP_TESTS %}Run integration tests{% else %}Skip tests{% endif %}"
depends_on = ["deploy_all"]
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                variables = {"SERVICES": ["api", "worker"], "ENVIRONMENT": "prod", "SKIP_TESTS": False}
                runbook = self.parser.parse(f.name, variables=variables)

                assert "deploy_all" in runbook.nodes
                assert "conditional_test" in runbook.nodes

                deploy_node = runbook.nodes["deploy_all"]
                assert deploy_node.command_name == "deploy api --env=prod && deploy worker --env=prod && echo 'All services deployed'"
                assert deploy_node.description == "Deploy all services: api, worker"
                assert deploy_node.skip is False

                test_node = runbook.nodes["conditional_test"]
                assert test_node.command_name == "run-tests --env=prod"
                assert test_node.description == "Run integration tests"
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_nested_data_when_parsing_then_substitutes_recursively(self):
        """Test parsing substitutes variables in nested data structures."""
        toml_content = """
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
TIMEOUT = { default = 300, type = "int", description = "Timeout" }

[runbook]
title = "Deploy {{APP_NAME}}"
description = "Deploy application"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[function_node]
type = "Function"
function_name = "notify"
description = "Send notification"
depends_on = []

[function_node.function_params]
message = "Deploying {{APP_NAME}}"
timeout = "{{TIMEOUT}}"
app = "{{APP_NAME}}"
env = "production"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                variables = {"APP_NAME": "testapp", "TIMEOUT": 600}
                runbook = self.parser.parse(f.name, variables=variables)

                function_node = runbook.nodes["function_node"]
                assert function_node.function_params["message"] == "Deploying testapp"
                assert function_node.function_params["timeout"] == "600"
                assert function_node.function_params["app"] == "testapp"
                assert function_node.function_params["env"] == "production"
            finally:
                Path(f.name).unlink()

    def test_given_runbook_when_getting_variable_definitions_then_returns_definitions(self):
        """Test extracting variable definitions without full parsing."""
        toml_content = """
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
PORT = { default = 8080, type = "int", min = 1024, max = 65535 }
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }

[runbook]
title = "Test"
description = "Test"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Manual"
description = "Start"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                definitions = self.parser.get_variable_definitions(f.name)

                assert len(definitions) == 3

                app_def = definitions["APP_NAME"]
                assert app_def.default == "myapp"
                assert app_def.description == "Application name"

                port_def = definitions["PORT"]
                assert port_def.default == 8080
                assert port_def.type == "int"
                assert port_def.min == 1024
                assert port_def.max == 65535

                env_def = definitions["ENVIRONMENT"]
                assert env_def.required is True
                assert env_def.choices == ["dev", "staging", "prod"]
            finally:
                Path(f.name).unlink()

    def test_given_runbook_with_simple_variable_syntax_when_parsing_then_creates_definition(self):
        """Test simple variable syntax creates proper definition."""
        toml_content = """
[variables]
APP_NAME = "myapp"
PORT = 8080
DEBUG = true

[runbook]
title = "{{APP_NAME}}"
description = "Test"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[start]
type = "Manual"
description = "Start"
depends_on = []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(toml_content)
            f.flush()

            try:
                definitions = self.parser.get_variable_definitions(f.name)

                assert definitions["APP_NAME"].default == "myapp"
                assert definitions["PORT"].default == 8080
                assert definitions["DEBUG"].default is True

                # Test parsing works with these definitions
                runbook = self.parser.parse(f.name)
                assert runbook.title == "myapp"
            finally:
                Path(f.name).unlink()