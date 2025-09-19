# tests/test_cli/test_commands/test_version.py
"""Tests for the version command."""


from playbook.cli.main import app


class TestVersionCommand:
    """Test cases for the version command."""

    def test_version_command(self, cli_runner):
        """Test version command output."""
        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "0.6.0" in result.output

    def test_version_flag(self, cli_runner):
        """Test version flag."""
        result = cli_runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "0.6.0" in result.output

    def test_version_short_flag(self, cli_runner):
        """Test version short flag."""
        result = cli_runner.invoke(app, ["-V"])

        assert result.exit_code == 0
        assert "0.6.0" in result.output
