# tests/test_cli/test_commands/test_version.py
"""Tests for the version command."""

import re
from unittest.mock import patch

from playbook.cli.main import app


class TestVersionCommand:
    """Test cases for the version command."""

    def test_version_command(self, cli_runner):
        """Test version command output."""
        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        # Test that output contains a version-like string (semantic versioning pattern or "unknown")
        version_pattern = r'(\d+\.\d+\.\d+|unknown)'
        assert re.search(version_pattern, result.output)

    def test_version_flag(self, cli_runner):
        """Test version flag."""
        result = cli_runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        version_pattern = r'(\d+\.\d+\.\d+|unknown)'
        assert re.search(version_pattern, result.output)

    def test_version_short_flag(self, cli_runner):
        """Test version short flag."""
        result = cli_runner.invoke(app, ["-V"])

        assert result.exit_code == 0
        version_pattern = r'(\d+\.\d+\.\d+|unknown)'
        assert re.search(version_pattern, result.output)

    @patch('playbook.cli.commands.version.metadata.version')
    def test_version_with_mocked_metadata(self, mock_version, cli_runner):
        """Test version command with mocked package metadata."""
        mock_version.return_value = "2.3.4"

        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "2.3.4" in result.output

    @patch('playbook.cli.commands.version.metadata.version')
    def test_version_with_package_not_found(self, mock_version, cli_runner):
        """Test version command when package metadata is not found."""
        from importlib.metadata import PackageNotFoundError
        mock_version.side_effect = PackageNotFoundError()

        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "unknown" in result.output
