# tests/conftest.py
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from playbook.domain.models import NodeExecution, NodeStatus, Runbook, Node, NodeType


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_runbook():
    """Sample runbook for testing"""
    return Runbook(
        title="Test Workflow",
        description="Test workflow for unit tests",
        version="0.1.0",
        author="test",
        created_at=datetime.now(timezone.utc),
        nodes={
            "step1": Node(
                id="step1",
                type=NodeType.COMMAND,
                command_name="echo 'step1'",
                description="First step",
                depends_on=[],
                critical=True
            ),
            "step2": Node(
                id="step2",
                type=NodeType.COMMAND,
                command_name="echo 'step2'",
                description="Second step",
                depends_on=["step1"],
                critical=False
            )
        }
    )


@pytest.fixture
def sample_node_execution():
    """Sample node execution for testing"""
    return NodeExecution(
        workflow_name="Test Workflow",
        run_id=1,
        node_id="test_node",
        attempt=1,
        start_time=datetime.now(timezone.utc),
        status=NodeStatus.OK,
        result_text="Test completed successfully"
    )


@pytest.fixture
def failed_node_execution():
    """Sample failed node execution for testing"""
    return NodeExecution(
        workflow_name="Test Workflow",
        run_id=1,
        node_id="test_node",
        attempt=1,
        start_time=datetime.now(timezone.utc),
        status=NodeStatus.NOK,
        exception="Test failure",
        exit_code=1
    )


@pytest.fixture
def temp_workflow_file():
    """Create a temporary workflow file for CLI testing"""
    content = """
[runbook]
title = "Temp Test Workflow"
description = "Temporary workflow for testing"
version = "0.1.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[test_step]
type = "Command"
command_name = "echo 'test'"
description = "Simple test step"
depends_on = []
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    yield tmp_path

    # Cleanup
    Path(tmp_path).unlink(missing_ok=True)


class WorkflowTestHelpers:
    """Utility class for common test operations"""

    @staticmethod
    def create_node_executions(workflow_name: str, run_id: int, node_id: str,
                              attempts: int, final_status: NodeStatus = NodeStatus.OK):
        """Create a sequence of node executions for retry testing"""
        executions = []
        base_time = datetime.now(timezone.utc)

        for attempt in range(1, attempts + 1):
            status = NodeStatus.NOK if attempt < attempts else final_status
            exception = f"Attempt {attempt} failed" if status == NodeStatus.NOK else None

            execution = NodeExecution(
                workflow_name=workflow_name,
                run_id=run_id,
                node_id=node_id,
                attempt=attempt,
                start_time=base_time,
                status=status,
                exception=exception
            )
            executions.append(execution)

        return executions

    @staticmethod
    def mock_user_responses(responses: list):
        """Helper to mock sequential user responses for interactive testing"""
        from unittest.mock import Mock
        mock = Mock()
        mock.side_effect = responses
        return mock


@pytest.fixture
def workflow_helpers():
    """Provide workflow test helpers"""
    return WorkflowTestHelpers