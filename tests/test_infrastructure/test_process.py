# tests/test_infrastructure/test_process.py
"""Tests for the process runner."""

from unittest.mock import patch, Mock
import subprocess

import pytest

from playbook.infrastructure.process import ShellProcessRunner


class TestShellProcessRunner:
    """Test cases for the ShellProcessRunner."""

    @pytest.fixture
    def runner(self):
        """Create a process runner instance."""
        return ShellProcessRunner()

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run, runner):
        """Test successful command execution."""
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        exit_code, stdout, stderr = runner.run_command("echo 'hello'", timeout=30)

        assert exit_code == 0
        assert stdout == "command output"
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run, runner):
        """Test failed command execution."""
        # Mock failed subprocess result
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_run.return_value = mock_result

        exit_code, stdout, stderr = runner.run_command("false", timeout=30)

        assert exit_code == 1
        assert stdout == ""
        assert stderr == "command failed"

    @patch("subprocess.run")
    def test_run_command_timeout(self, mock_run, runner):
        """Test command timeout."""
        # Mock timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        exit_code, stdout, stderr = runner.run_command("sleep 60", timeout=30)

        assert exit_code == 1  # Process runner returns 1 for timeout
        assert "timed out after 30 seconds" in stderr.lower()

    @patch("subprocess.run")
    def test_run_command_with_environment_expansion(self, mock_run, runner):
        """Test command with environment variable expansion."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "expanded"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with patch(
            "os.path.expandvars", return_value="expanded_command"
        ) as mock_expandvars:
            with patch(
                "os.path.expanduser", return_value="user_expanded"
            ) as mock_expanduser:
                runner.run_command("$HOME/script", timeout=30)

                mock_expandvars.assert_called_once_with("$HOME/script")
                mock_expanduser.assert_called_once_with("expanded_command")

    @patch("subprocess.run")
    def test_run_command_exception(self, mock_run, runner):
        """Test command execution with unexpected exception."""
        mock_run.side_effect = OSError("Permission denied")

        exit_code, stdout, stderr = runner.run_command("restricted_command", timeout=30)

        assert exit_code == 1
        assert stdout == ""
        assert "Permission denied" in stderr

    @patch("subprocess.Popen")
    @patch("sys.stdin")
    @patch("termios.tcgetattr")
    @patch("os.setsid")
    def test_run_interactive_command_simple(
        self, mock_setsid, mock_tcgetattr, mock_stdin, mock_popen, runner
    ):
        """Test interactive command execution (simplified)."""
        # Mock terminal setup
        mock_stdin.fileno.return_value = 0
        mock_tcgetattr.return_value = "old_settings"

        # Mock successful interactive subprocess result
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None  # wait() completes successfully
        mock_popen.return_value = mock_process

        exit_code, stdout, stderr = runner.run_command(
            "interactive_cmd", timeout=30, interactive=True
        )

        assert exit_code == 0
        assert stdout == ""
        assert stderr == ""
        mock_popen.assert_called_once()

    def test_run_command_types(self, runner):
        """Test that run_command returns correct types."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = "error"
            mock_run.return_value = mock_result

            exit_code, stdout, stderr = runner.run_command("test", timeout=30)

            assert isinstance(exit_code, int)
            assert isinstance(stdout, str)
            assert isinstance(stderr, str)
