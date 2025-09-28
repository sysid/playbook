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
plugin = "python"
function = "notify"
function_params = { "message" = "Test notification" }
description = "Notification function"
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
        assert function_node.plugin == "python"
        assert function_node.function == "notify"
        assert function_node.function_params == {"message": "Test notification"}
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

    def test_implicit_linear_dependencies(self, parser, temp_dir):
        """Test implicit linear dependencies when depends_on is omitted."""
        content = """
[runbook]
title = "Linear Workflow"
description = "Test linear workflow"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[step1]
type = "Command"
command_name = "echo 'First step'"

[step2]
type = "Command"
command_name = "echo 'Second step'"

[step3]
type = "Command"
command_name = "echo 'Third step'"
"""
        toml_file = temp_dir / "linear.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # First step should have no dependencies
        assert runbook.nodes["step1"].depends_on == []

        # Second step should depend on first
        assert runbook.nodes["step2"].depends_on == ["step1"]

        # Third step should depend on second
        assert runbook.nodes["step3"].depends_on == ["step2"]

    def test_string_dependency_normalization(self, parser, temp_dir):
        """Test that string dependencies are normalized to lists."""
        content = """
[runbook]
title = "String Deps"
description = "Test string dependencies"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[step1]
type = "Command"
command_name = "echo 'First step'"
depends_on = []

[step2]
type = "Command"
command_name = "echo 'Second step'"
depends_on = "step1"
"""
        toml_file = temp_dir / "string_deps.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # step2 should have step1 as dependency (string converted to list)
        assert runbook.nodes["step2"].depends_on == ["step1"]

    def test_caret_keyword_dependency(self, parser, temp_dir):
        """Test ^ keyword for previous node dependency."""
        content = """
[runbook]
title = "Caret Dependencies"
description = "Test caret keyword"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[step1]
type = "Command"
command_name = "echo 'First step'"

[step2]
type = "Command"
command_name = "echo 'Second step'"
depends_on = "^"

[step3]
type = "Command"
command_name = "echo 'Third step'"
depends_on = "^"
"""
        toml_file = temp_dir / "caret_deps.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # First step should have no dependencies
        assert runbook.nodes["step1"].depends_on == []

        # step2 should depend on step1 (previous node)
        assert runbook.nodes["step2"].depends_on == ["step1"]

        # step3 should depend on step2 (previous node)
        assert runbook.nodes["step3"].depends_on == ["step2"]

    def test_star_keyword_dependency(self, parser, temp_dir):
        """Test * keyword for all previous nodes dependency."""
        content = """
[runbook]
title = "Star Dependencies"
description = "Test star keyword"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[step1]
type = "Command"
command_name = "echo 'First step'"

[step2]
type = "Command"
command_name = "echo 'Second step'"

[final]
type = "Command"
command_name = "echo 'Final step'"
depends_on = "*"
"""
        toml_file = temp_dir / "star_deps.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # First step should have no dependencies (implicit)
        assert runbook.nodes["step1"].depends_on == []

        # Second step should depend on first (implicit)
        assert runbook.nodes["step2"].depends_on == ["step1"]

        # Final step should depend on all previous nodes
        assert runbook.nodes["final"].depends_on == ["step1", "step2"]

    def test_mixed_keywords_in_list(self, parser, temp_dir):
        """Test mixing special keywords with regular dependencies in a list."""
        content = """
[runbook]
title = "Mixed Dependencies"
description = "Test mixed keywords"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[step1]
type = "Command"
command_name = "echo 'First step'"

[step2]
type = "Command"
command_name = "echo 'Second step'"

[other]
type = "Command"
command_name = "echo 'Other step'"
depends_on = []

[final]
type = "Command"
command_name = "echo 'Final step'"
depends_on = ["^", "step1"]
"""
        toml_file = temp_dir / "mixed_deps.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # Final step should depend on previous node (other) and step1
        expected_deps = ["other", "step1"]
        assert sorted(runbook.nodes["final"].depends_on) == sorted(expected_deps)

    def test_caret_keyword_first_node(self, parser, temp_dir):
        """Test ^ keyword on first node (should result in no dependencies)."""
        content = """
[runbook]
title = "First Node Caret"
description = "Test caret on first node"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[first]
type = "Command"
command_name = "echo 'First step'"
depends_on = "^"
"""
        toml_file = temp_dir / "first_caret.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # First node with ^ should have no dependencies
        assert runbook.nodes["first"].depends_on == []

    def test_star_keyword_first_node(self, parser, temp_dir):
        """Test * keyword on first node (should result in no dependencies)."""
        content = """
[runbook]
title = "First Node Star"
description = "Test star on first node"
version = "1.0.0"
author = "Test Author"
created_at = "2025-01-20T12:00:00Z"

[first]
type = "Command"
command_name = "echo 'First step'"
depends_on = "*"
"""
        toml_file = temp_dir / "first_star.playbook.toml"
        toml_file.write_text(content)

        runbook = parser.parse(str(toml_file))

        # First node with * should have no dependencies
        assert runbook.nodes["first"].depends_on == []
