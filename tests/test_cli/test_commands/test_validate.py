"""Tests for the validate command."""

from playbook.cli.main import app


def test_validate_success(cli_runner, temp_toml_file):
    result = cli_runner.invoke(app, ["validate", temp_toml_file])

    assert result.exit_code == 0
    assert "Runbook is valid" in result.output
    assert "Test Workflow" in result.output
    assert "Steps: 1" in result.output
    assert "Command: 1" in result.output


def test_validate_parse_error(cli_runner, temp_dir):
    invalid = temp_dir / "invalid.playbook.toml"
    invalid.write_text("schema_version = 3\n")

    result = cli_runner.invoke(app, ["validate", str(invalid)])

    assert result.exit_code == 1
    assert "runbook" in result.output.lower()


def test_validate_file_not_found(cli_runner):
    result = cli_runner.invoke(app, ["validate", "/nonexistent/file.toml"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_validate_accepts_required_variables(cli_runner, temp_dir):
    workflow = temp_dir / "required.playbook.toml"
    workflow.write_text(
        """
schema_version = 3
[variables]
ENVIRONMENT = { required = true }
[runbook]
id = "required"
title = "Required"
[[steps]]
id = "review"
type = "manual"
instructions = "Review {{ ENVIRONMENT }}"
"""
    )

    result = cli_runner.invoke(
        app,
        ["validate", str(workflow), "--var", "ENVIRONMENT=test"],
    )

    assert result.exit_code == 0
    assert "Runbook is valid" in result.output
