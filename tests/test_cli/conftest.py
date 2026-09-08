# tests/test_cli/conftest.py
"""CLI-specific test fixtures."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_toml_content():
    """Sample TOML content for testing."""
    return """
schema_version = 3

[runbook]
id = "test-workflow"
title = "Test Workflow"
description = "Test workflow for CLI testing"
version = "0.1.0"
author = "test"

[[steps]]
id = "test-step"
type = "command"
command = "echo 'test'"
instructions = "Simple test step"
"""


@pytest.fixture
def temp_toml_file(sample_toml_content):
    """Create a temporary TOML file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".playbook.toml", delete=False
    ) as tmp:
        tmp.write(sample_toml_content)
        tmp_path = tmp.name

    yield tmp_path

    # Cleanup
    Path(tmp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)
