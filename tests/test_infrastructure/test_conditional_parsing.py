# tests/test_infrastructure/test_conditional_parsing.py
"""Tests for conditional dependency parsing in TOML files."""

import pytest
import tempfile
import os
from datetime import datetime

from src.playbook.infrastructure.parser import RunbookParser
from src.playbook.infrastructure.variables import VariableManager


class TestConditionalParsing:
    def setup_method(self):
        """Set up test fixtures."""
        self.variable_manager = VariableManager(interactive=False)
        self.parser = RunbookParser(self.variable_manager)

    def create_temp_playbook(self, content: str) -> str:
        """Create a temporary playbook file with given content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".playbook.toml", delete=False
        ) as f:
            f.write(content)
            return f.name

    def teardown_method(self):
        """Clean up temporary files."""
        pass

    def test_parse_simple_when_clause(self):
        """Test parsing runbook with simple when clause."""
        toml_content = """
[runbook]
title = "Conditional Test"
description = "Test conditional execution"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build"]
when = "{{ ENVIRONMENT == 'prod' }}"
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path, {"ENVIRONMENT": "prod"})

            assert len(runbook.nodes) == 2
            assert "build" in runbook.nodes
            assert "deploy" in runbook.nodes

            deploy_node = runbook.nodes["deploy"]
            assert deploy_node.when == "{{ ENVIRONMENT == 'prod' }}"
            assert deploy_node.depends_on == ["build"]

        finally:
            os.unlink(file_path)

    def test_parse_conditional_dependencies_success(self):
        """Test parsing conditional dependencies with success condition."""
        toml_content = """
[runbook]
title = "Conditional Dependencies Test"
description = "Test conditional dependencies"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[test]
type = "Command"
command_name = "make test"
depends_on = ["build"]

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["test:success"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path)

            deploy_node = runbook.nodes["deploy"]
            assert deploy_node.depends_on == ["test"]
            assert 'has_succeeded("test")' in deploy_node.when

        finally:
            os.unlink(file_path)

    def test_parse_conditional_dependencies_failure(self):
        """Test parsing conditional dependencies with failure condition."""
        toml_content = """
[runbook]
title = "Conditional Dependencies Test"
description = "Test conditional dependencies"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = []

[rollback]
type = "Command"
command_name = "make rollback"
depends_on = ["deploy:failure"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path)

            rollback_node = runbook.nodes["rollback"]
            assert rollback_node.depends_on == ["deploy"]
            assert 'has_failed("deploy")' in rollback_node.when

        finally:
            os.unlink(file_path)

    def test_parse_mixed_conditional_dependencies(self):
        """Test parsing mixed conditional and regular dependencies."""
        toml_content = """
[runbook]
title = "Mixed Dependencies Test"
description = "Test mixed dependencies"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[test]
type = "Command"
command_name = "make test"
depends_on = []

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build", "test:success"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path)

            deploy_node = runbook.nodes["deploy"]
            assert deploy_node.depends_on == ["build", "test"]
            assert 'has_succeeded("test")' in deploy_node.when

        finally:
            os.unlink(file_path)

    def test_parse_multiple_conditional_dependencies(self):
        """Test parsing multiple conditional dependencies."""
        toml_content = """
[runbook]
title = "Multiple Conditional Dependencies"
description = "Test multiple conditional dependencies"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[test]
type = "Command"
command_name = "make test"
depends_on = []

[security_scan]
type = "Command"
command_name = "security scan"
depends_on = []

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build:success", "test:success", "security_scan:success"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path)

            deploy_node = runbook.nodes["deploy"]
            assert deploy_node.depends_on == ["build", "test", "security_scan"]
            # Check that all success conditions are combined with AND
            assert 'has_succeeded("build")' in deploy_node.when
            assert 'has_succeeded("test")' in deploy_node.when
            assert 'has_succeeded("security_scan")' in deploy_node.when
            assert "and" in deploy_node.when

        finally:
            os.unlink(file_path)

    def test_parse_when_clause_with_conditional_dependencies(self):
        """Test combining explicit when clause with conditional dependencies."""
        toml_content = """
[runbook]
title = "Combined Conditions Test"
description = "Test combined conditions"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build:success"]
when = "{{ ENVIRONMENT == 'prod' }}"
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path, {"ENVIRONMENT": "prod"})

            deploy_node = runbook.nodes["deploy"]
            assert deploy_node.depends_on == ["build"]
            # Check that both conditions are combined
            assert "ENVIRONMENT == 'prod'" in deploy_node.when
            assert 'has_succeeded("build")' in deploy_node.when
            assert "and" in deploy_node.when

        finally:
            os.unlink(file_path)

    def test_parse_invalid_conditional_dependency(self):
        """Test parsing invalid conditional dependency."""
        toml_content = """
[runbook]
title = "Invalid Conditional Test"
description = "Test invalid conditional dependency"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build:invalid"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            with pytest.raises(ValueError, match="Invalid condition 'invalid'"):
                self.parser.parse(file_path)

        finally:
            os.unlink(file_path)

    def test_parse_runbook_with_variable_in_when_clause(self):
        """Test parsing runbook with variables in when clause."""
        toml_content = """
[variables]
ENVIRONMENT = { default = "dev", choices = ["dev", "staging", "prod"] }
ENABLE_DEPLOY = { default = true, type = "bool" }

[runbook]
title = "Variable Conditional Test"
description = "Test variables in conditions"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build"]
when = "{{ ENVIRONMENT == 'prod' and ENABLE_DEPLOY }}"
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            # Test with variables that should enable deployment
            runbook = self.parser.parse(
                file_path, {"ENVIRONMENT": "prod", "ENABLE_DEPLOY": True}
            )

            deploy_node = runbook.nodes["deploy"]
            assert "ENVIRONMENT == 'prod'" in deploy_node.when
            assert "ENABLE_DEPLOY" in deploy_node.when

        finally:
            os.unlink(file_path)

    def test_backward_compatibility_simple_dependencies(self):
        """Test that simple dependencies still work without conditions."""
        toml_content = """
[runbook]
title = "Backward Compatibility Test"
description = "Test backward compatibility"
version = "1.0.0"
author = "test"
created_at = "2025-01-01T12:00:00Z"

[build]
type = "Command"
command_name = "make build"
depends_on = []

[test]
type = "Command"
command_name = "make test"
depends_on = ["build"]

[deploy]
type = "Command"
command_name = "make deploy"
depends_on = ["build", "test"]
"""

        file_path = self.create_temp_playbook(toml_content)
        try:
            runbook = self.parser.parse(file_path)

            # All nodes should have default when="true"
            for node_id, node in runbook.nodes.items():
                assert node.when == "true"

            # Dependencies should be preserved
            assert runbook.nodes["test"].depends_on == ["build"]
            assert runbook.nodes["deploy"].depends_on == ["build", "test"]

        finally:
            os.unlink(file_path)
