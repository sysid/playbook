# tests/test_infrastructure/test_parser.py
"""Tests for the TOML parser."""

import tempfile
from pathlib import Path

import pytest

from playbook.infrastructure.parser import RunbookParser
from playbook.domain.models import NodeType


class TestRunbookParser:
    """Test cases for the RunbookParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return RunbookParser()

    @pytest.fixture
    def valid_toml_content(self):
        """Valid TOML content for testing."""
        return """
[runbook]
title = "Test Workflow"
description = "Test workflow description"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[manual_step]
type = "Manual"
description = "Manual approval step"
prompt_after = "Proceed with deployment?"
depends_on = []
critical = true

[command_step]
type = "Command"
command_name = "echo 'hello'"
description = "Echo command"
depends_on = ["manual_step"]
timeout = 300

[function_step]
type = "Function"
function_name = "mymodule.myfunction"
function_params = { "param1" = "value1", "param2" = 42 }
description = "Function call"
depends_on = ["command_step"]
"""

    @pytest.fixture
    def invalid_toml_missing_runbook(self):
        """TOML missing runbook section."""
        return """
[manual_step]
type = "Manual"
description = "Manual step"
depends_on = []
"""

    @pytest.fixture
    def invalid_toml_missing_fields(self):
        """TOML missing required fields."""
        return """
[runbook]
title = "Test Workflow"
# Missing other required fields

[step1]
type = "Manual"
depends_on = []
"""

    def test_parse_valid_toml(self, parser, valid_toml_content, temp_dir):
        """Test parsing valid TOML file."""
        toml_file = temp_dir / "valid.playbook.toml"
        toml_file.write_text(valid_toml_content)

        runbook = parser.parse(str(toml_file))

        assert runbook.title == "Test Workflow"
        assert runbook.description == "Test workflow description"
        assert runbook.version == "1.0.0"
        assert runbook.author == "Test Author"
        assert len(runbook.nodes) == 3

        # Check manual node
        manual_node = runbook.nodes["manual_step"]
        assert manual_node.type == NodeType.MANUAL
        assert manual_node.critical is True
        assert manual_node.depends_on == []

        # Check command node
        command_node = runbook.nodes["command_step"]
        assert command_node.type == NodeType.COMMAND
        assert command_node.command_name == "echo 'hello'"
        assert command_node.depends_on == ["manual_step"]
        assert command_node.timeout == 300

        # Check function node
        function_node = runbook.nodes["function_step"]
        assert function_node.type == NodeType.FUNCTION
        assert function_node.function_name == "mymodule.myfunction"
        assert function_node.function_params == {"param1": "value1", "param2": 42}
        assert function_node.depends_on == ["command_step"]

    def test_parse_file_not_found(self, parser):
        """Test parsing non-existent file."""
        with pytest.raises(FileNotFoundError, match="Runbook file not found"):
            parser.parse("/nonexistent/file.toml")

    def test_parse_wrong_extension(self, parser, temp_dir):
        """Test parsing file with wrong extension."""
        wrong_file = temp_dir / "wrong.txt"
        wrong_file.write_text("[runbook]\ntitle = 'test'")

        with pytest.raises(
            ValueError, match="Runbook file must have a .playbook.toml extension"
        ):
            parser.parse(str(wrong_file))

    def test_parse_missing_runbook_section(
        self, parser, invalid_toml_missing_runbook, temp_dir
    ):
        """Test parsing TOML missing runbook section."""
        toml_file = temp_dir / "missing_runbook.playbook.toml"
        toml_file.write_text(invalid_toml_missing_runbook)

        with pytest.raises(ValueError, match="Missing required \\[runbook\\] section"):
            parser.parse(str(toml_file))

    def test_parse_missing_required_fields(
        self, parser, invalid_toml_missing_fields, temp_dir
    ):
        """Test parsing TOML missing required fields."""
        toml_file = temp_dir / "missing_fields.playbook.toml"
        toml_file.write_text(invalid_toml_missing_fields)

        with pytest.raises(ValueError, match="Missing required field in \\[runbook\\]"):
            parser.parse(str(toml_file))

    def test_parse_invalid_toml_syntax(self, parser, temp_dir):
        """Test parsing invalid TOML syntax."""
        invalid_content = """
[runbook
title = "Test" # Missing closing bracket
"""
        toml_file = temp_dir / "invalid_syntax.playbook.toml"
        toml_file.write_text(invalid_content)

        with pytest.raises(Exception):  # tomllib will raise a parsing error
            parser.parse(str(toml_file))

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)
