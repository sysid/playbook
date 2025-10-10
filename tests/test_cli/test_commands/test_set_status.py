# tests/test_cli/test_commands/test_set_status.py
"""Tests for the set-status command."""

from datetime import datetime, timezone
from unittest.mock import patch, Mock

from playbook.cli.main import app
from playbook.domain.models import RunStatus, RunInfo, TriggerType


class TestSetStatusCommand:
    """Test cases for the set-status command."""

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    @patch("playbook.cli.commands.set_status.Confirm.ask")
    def test_set_status_when_valid_then_updates_status(
        self,
        mock_confirm,
        mock_get_engine,
        mock_parser_class,
        cli_runner,
        temp_toml_file,
    ):
        """Test successful status update."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        # Mock confirmation
        mock_confirm.return_value = True

        result = cli_runner.invoke(app, ["set-status", temp_toml_file, "42", "aborted"])

        assert result.exit_code == 0
        assert "Status updated to ABORTED" in result.output
        mock_engine.run_repo.update_run.assert_called_once()

        # Verify status was changed
        updated_run_info = mock_engine.run_repo.update_run.call_args[0][0]
        assert updated_run_info.status == RunStatus.ABORTED

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    def test_set_status_when_invalid_status_then_shows_error(
        self, mock_get_engine, mock_parser_class, cli_runner, temp_toml_file
    ):
        """Test invalid status string."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        result = cli_runner.invoke(
            app, ["set-status", temp_toml_file, "42", "invalid_status"]
        )

        assert result.exit_code == 1
        assert "Invalid status" in result.output
        assert "Valid statuses" in result.output

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    def test_set_status_when_run_not_found_then_shows_error(
        self, mock_get_engine, mock_parser_class, cli_runner, temp_toml_file
    ):
        """Test non-existent run_id."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine to raise error
        mock_engine = Mock()
        mock_engine.run_repo.get_run.side_effect = ValueError("Run not found")
        mock_get_engine.return_value = mock_engine

        result = cli_runner.invoke(
            app, ["set-status", temp_toml_file, "999", "aborted"]
        )

        assert result.exit_code != 0
        assert "DatabaseError" in result.output

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    @patch("playbook.cli.commands.set_status.Confirm.ask")
    def test_set_status_when_terminal_to_nonterminal_then_warns(
        self,
        mock_confirm,
        mock_get_engine,
        mock_parser_class,
        cli_runner,
        temp_toml_file,
    ):
        """Test warning when changing from terminal to non-terminal state."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine with completed run
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.OK,  # Terminal state
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        # Mock confirmation
        mock_confirm.return_value = True

        result = cli_runner.invoke(app, ["set-status", temp_toml_file, "42", "running"])

        assert result.exit_code == 0
        assert "⚠️" in result.output
        assert "terminal state" in result.output

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    def test_set_status_when_force_then_skips_confirmation(
        self, mock_get_engine, mock_parser_class, cli_runner, temp_toml_file
    ):
        """Test force flag skips confirmation."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        result = cli_runner.invoke(
            app, ["set-status", temp_toml_file, "42", "aborted", "--force"]
        )

        assert result.exit_code == 0
        assert "Status updated to ABORTED" in result.output
        mock_engine.run_repo.update_run.assert_called_once()

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    @patch("playbook.cli.commands.set_status.Confirm.ask")
    def test_set_status_case_insensitive(
        self,
        mock_confirm,
        mock_get_engine,
        mock_parser_class,
        cli_runner,
        temp_toml_file,
    ):
        """Test case-insensitive status handling."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        # Mock confirmation
        mock_confirm.return_value = True

        # Test with different cases
        for status_str in ["ABORTED", "aborted", "Aborted"]:
            result = cli_runner.invoke(
                app, ["set-status", temp_toml_file, "42", status_str]
            )

            assert result.exit_code == 0

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    @patch("playbook.cli.commands.set_status.Confirm.ask")
    def test_set_status_when_user_cancels_then_exits(
        self,
        mock_confirm,
        mock_get_engine,
        mock_parser_class,
        cli_runner,
        temp_toml_file,
    ):
        """Test user canceling the operation."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        # Mock confirmation to return False
        mock_confirm.return_value = False

        result = cli_runner.invoke(app, ["set-status", temp_toml_file, "42", "aborted"])

        # User cancellation is not an error, but we exit gracefully
        assert result.exit_code in [0, 1]  # Typer may return 0 or 1 for graceful exit
        assert "Operation cancelled" in result.output
        mock_engine.run_repo.update_run.assert_not_called()

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    def test_set_status_when_same_status_then_no_change(
        self, mock_get_engine, mock_parser_class, cli_runner, temp_toml_file
    ):
        """Test setting to same status."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.ABORTED,  # Already aborted
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        result = cli_runner.invoke(app, ["set-status", temp_toml_file, "42", "aborted"])

        assert result.exit_code == 0
        assert "Status is already ABORTED" in result.output
        assert "No change needed" in result.output
        mock_engine.run_repo.update_run.assert_not_called()

    @patch("playbook.cli.commands.set_status.RunbookParser")
    @patch("playbook.cli.commands.set_status.get_engine")
    @patch("playbook.cli.commands.set_status.Confirm.ask")
    def test_set_status_when_aborted_then_shows_resume_hint(
        self,
        mock_confirm,
        mock_get_engine,
        mock_parser_class,
        cli_runner,
        temp_toml_file,
    ):
        """Test helpful hint after setting to ABORTED."""
        # Mock parser
        mock_parser = Mock()
        mock_runbook = Mock()
        mock_runbook.title = "Test Workflow"
        mock_parser.parse.return_value = mock_runbook
        mock_parser_class.return_value = mock_parser

        # Mock engine and run info
        mock_engine = Mock()
        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=42,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )
        mock_engine.run_repo.get_run.return_value = run_info
        mock_get_engine.return_value = mock_engine

        # Mock confirmation
        mock_confirm.return_value = True

        result = cli_runner.invoke(app, ["set-status", temp_toml_file, "42", "aborted"])

        assert result.exit_code == 0
        assert "playbook resume" in result.output
