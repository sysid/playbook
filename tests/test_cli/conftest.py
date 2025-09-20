# tests/test_cli/conftest.py
"""CLI-specific test fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from playbook.cli.main import app


@pytest.fixture
def cli_runner():
    """Provide a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_toml_content():
    """Sample TOML content for testing."""
    return """
[runbook]
title = "Test Workflow"
description = "Test workflow for CLI testing"
version = "0.1.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[test_step]
type = "Command"
command_name = "echo 'test'"
description = "Simple test step"
depends_on = []
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


@pytest.fixture
def mock_engine():
    """Mock engine for CLI testing."""
    engine = Mock()
    engine.validate.return_value = []  # No validation errors
    return engine


@pytest.fixture
def mock_parser():
    """Mock parser for CLI testing."""
    parser = Mock()
    return parser


@pytest.fixture
def cli_app():
    """Provide the CLI app for testing."""
    return app
