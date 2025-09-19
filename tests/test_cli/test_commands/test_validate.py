# tests/test_cli/test_commands/test_validate.py
"""Tests for the validate command."""

from unittest.mock import patch, Mock


from playbook.cli.main import app


class TestValidateCommand:
    """Test cases for the validate command."""

    @patch("playbook.cli.commands.validate.get_parser")
    @patch("playbook.cli.commands.validate.get_engine")
    def test_validate_success(
        self, mock_get_engine, mock_get_parser, cli_runner, temp_toml_file
    ):
        """Test successful validation."""
        # Mock the parser and engine
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_runbook.description = "Test Description"
        mock_runbook.version = "1.0.0"
        mock_runbook.author = "Test Author"
        mock_runbook.created_at.isoformat.return_value = "2025-01-20T12:00:00Z"
        mock_runbook.nodes = {"node1": Mock(), "node2": Mock()}

        # Configure node types for counting
        from playbook.domain.models import NodeType

        mock_runbook.nodes["node1"].type = NodeType.MANUAL
        mock_runbook.nodes["node1"].skip = False
        mock_runbook.nodes["node2"].type = NodeType.COMMAND
        mock_runbook.nodes["node2"].skip = False

        mock_parser.parse.return_value = mock_runbook
        mock_parser.get_variable_definitions.return_value = {}  # No variables defined
        mock_get_parser.return_value = mock_parser

        mock_engine = Mock()
        mock_engine.validate.return_value = []  # No errors
        mock_get_engine.return_value = mock_engine

        result = cli_runner.invoke(app, ["validate", temp_toml_file])

        assert result.exit_code == 0
        assert "Runbook is valid!" in result.output
        assert "Test Workflow" in result.output
        mock_parser.parse.assert_called_once_with(temp_toml_file, variables={})
        mock_engine.validate.assert_called_once_with(mock_runbook)

    @patch("playbook.cli.commands.validate.get_parser")
    @patch("playbook.cli.commands.validate.get_engine")
    def test_validate_with_errors(
        self, mock_get_engine, mock_get_parser, cli_runner, temp_toml_file
    ):
        """Test validation with errors."""
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser.get_variable_definitions.return_value = {}  # No variables defined
        mock_get_parser.return_value = mock_parser

        mock_engine = Mock()
        mock_engine.validate.return_value = ["Error 1", "Error 2"]
        mock_get_engine.return_value = mock_engine

        result = cli_runner.invoke(app, ["validate", temp_toml_file])

        assert result.exit_code == 1
        # New error handling shows ValidationError in rich format
        assert "ValidationError" in result.output
        assert "validation error" in result.output

    @patch("playbook.cli.commands.validate.get_parser")
    def test_validate_parse_error(self, mock_get_parser, cli_runner, temp_toml_file):
        """Test validation with parse error."""
        mock_parser = Mock()
        mock_parser.parse.side_effect = Exception("Parse error")
        mock_parser.get_variable_definitions.return_value = {}  # No variables defined
        mock_get_parser.return_value = mock_parser

        result = cli_runner.invoke(app, ["validate", temp_toml_file])

        assert result.exit_code == 1
        # New error handling shows ParseError in rich format
        assert "ParseError" in result.output
        assert "Parse error" in result.output

    def test_validate_file_not_found(self, cli_runner):
        """Test validation with non-existent file."""
        result = cli_runner.invoke(app, ["validate", "/nonexistent/file.toml"])

        assert result.exit_code == 1
        # New error handling shows ParseError in rich format
        assert "ParseError" in result.output
        assert "not found" in result.output
