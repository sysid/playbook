# tests/test_infrastructure/test_persistence.py
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from playbook.domain.models import NodeExecution, NodeStatus
from playbook.infrastructure.persistence import SQLiteNodeExecutionRepository


class TestSQLiteNodeExecutionRepository:
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        repo = SQLiteNodeExecutionRepository(db_path)
        repo._init_db()

        yield repo

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_executions(self):
        """Create sample execution records for testing"""
        base_time = datetime.now(timezone.utc)

        return [
            NodeExecution(
                workflow_name="test_workflow",
                run_id=1,
                node_id="test_node",
                attempt=1,
                start_time=base_time,
                status=NodeStatus.NOK,
                exception="First attempt failed",
            ),
            NodeExecution(
                workflow_name="test_workflow",
                run_id=1,
                node_id="test_node",
                attempt=2,
                start_time=base_time,
                status=NodeStatus.NOK,
                exception="Second attempt failed",
            ),
            NodeExecution(
                workflow_name="test_workflow",
                run_id=1,
                node_id="test_node",
                attempt=3,
                start_time=base_time,
                status=NodeStatus.OK,
                result_text="Third attempt succeeded",
            ),
            # Different node in same workflow
            NodeExecution(
                workflow_name="test_workflow",
                run_id=1,
                node_id="other_node",
                attempt=1,
                start_time=base_time,
                status=NodeStatus.OK,
            ),
            # Same node in different run
            NodeExecution(
                workflow_name="test_workflow",
                run_id=2,
                node_id="test_node",
                attempt=1,
                start_time=base_time,
                status=NodeStatus.RUNNING,
            ),
        ]

    def test_get_latest_execution_attempt_when_no_executions_then_returns_none(
        self, temp_db
    ):
        """Test get_latest_execution_attempt returns None when no executions exist"""
        # Act
        result = temp_db.get_latest_execution_attempt(
            "test_workflow", 1, "nonexistent_node"
        )

        # Assert
        assert result is None

    def test_get_latest_execution_attempt_when_single_execution_then_returns_execution(
        self, temp_db, sample_executions
    ):
        """Test get_latest_execution_attempt returns the execution when only one exists"""
        # Arrange
        execution = sample_executions[0]  # Single execution with attempt=1
        temp_db.create_execution(execution)

        # Act
        result = temp_db.get_latest_execution_attempt("test_workflow", 1, "test_node")

        # Assert
        assert result is not None
        assert result.workflow_name == "test_workflow"
        assert result.run_id == 1
        assert result.node_id == "test_node"
        assert result.attempt == 1
        assert result.status == NodeStatus.NOK

    def test_get_latest_execution_attempt_when_multiple_attempts_then_returns_highest(
        self, temp_db, sample_executions
    ):
        """Test get_latest_execution_attempt returns the execution with highest attempt number"""
        # Arrange - Add first 3 executions (attempts 1, 2, 3)
        for execution in sample_executions[:3]:
            temp_db.create_execution(execution)

        # Act
        result = temp_db.get_latest_execution_attempt("test_workflow", 1, "test_node")

        # Assert
        assert result is not None
        assert result.attempt == 3  # Highest attempt
        assert result.status == NodeStatus.OK
        assert result.result_text == "Third attempt succeeded"

    def test_get_latest_execution_attempt_when_different_nodes_then_isolates_correctly(
        self, temp_db, sample_executions
    ):
        """Test get_latest_execution_attempt isolates between different nodes"""
        # Arrange - Add executions for different nodes
        for execution in sample_executions[:4]:  # Includes test_node and other_node
            temp_db.create_execution(execution)

        # Act
        result_test_node = temp_db.get_latest_execution_attempt(
            "test_workflow", 1, "test_node"
        )
        result_other_node = temp_db.get_latest_execution_attempt(
            "test_workflow", 1, "other_node"
        )

        # Assert
        assert result_test_node.node_id == "test_node"
        assert result_test_node.attempt == 3  # Highest attempt for test_node

        assert result_other_node.node_id == "other_node"
        assert result_other_node.attempt == 1  # Only attempt for other_node

    def test_get_latest_execution_attempt_when_different_runs_then_isolates_correctly(
        self, temp_db, sample_executions
    ):
        """Test get_latest_execution_attempt isolates between different runs"""
        # Arrange - Add executions for different runs
        for execution in [
            sample_executions[0],
            sample_executions[4],
        ]:  # Run 1 and Run 2
            temp_db.create_execution(execution)

        # Act
        result_run1 = temp_db.get_latest_execution_attempt(
            "test_workflow", 1, "test_node"
        )
        result_run2 = temp_db.get_latest_execution_attempt(
            "test_workflow", 2, "test_node"
        )

        # Assert
        assert result_run1.run_id == 1
        assert result_run1.attempt == 1
        assert result_run1.status == NodeStatus.NOK

        assert result_run2.run_id == 2
        assert result_run2.attempt == 1
        assert result_run2.status == NodeStatus.RUNNING

    def test_get_latest_execution_attempt_when_different_workflows_then_isolates_correctly(
        self, temp_db
    ):
        """Test get_latest_execution_attempt isolates between different workflows"""
        # Arrange
        execution1 = NodeExecution(
            workflow_name="workflow_a",
            run_id=1,
            node_id="test_node",
            attempt=2,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.OK,
        )
        execution2 = NodeExecution(
            workflow_name="workflow_b",
            run_id=1,
            node_id="test_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.NOK,
        )

        temp_db.create_execution(execution1)
        temp_db.create_execution(execution2)

        # Act
        result_a = temp_db.get_latest_execution_attempt("workflow_a", 1, "test_node")
        result_b = temp_db.get_latest_execution_attempt("workflow_b", 1, "test_node")

        # Assert
        assert result_a.workflow_name == "workflow_a"
        assert result_a.attempt == 2
        assert result_a.status == NodeStatus.OK

        assert result_b.workflow_name == "workflow_b"
        assert result_b.attempt == 1
        assert result_b.status == NodeStatus.NOK

    def test_get_latest_execution_attempt_preserves_all_fields(self, temp_db):
        """Test that get_latest_execution_attempt preserves all execution fields"""
        # Arrange
        execution = NodeExecution(
            workflow_name="test_workflow",
            run_id=1,
            node_id="test_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            status=NodeStatus.OK,
            operator_decision="approved",
            result_text="Test result",
            exit_code=0,
            exception=None,
            stdout="Test output",
            stderr="",
            duration_ms=1000,
        )
        temp_db.create_execution(execution)

        # Act
        result = temp_db.get_latest_execution_attempt("test_workflow", 1, "test_node")

        # Assert
        assert result.workflow_name == execution.workflow_name
        assert result.run_id == execution.run_id
        assert result.node_id == execution.node_id
        assert result.attempt == execution.attempt
        assert result.status == execution.status
        assert result.operator_decision == execution.operator_decision
        assert result.result_text == execution.result_text
        assert result.exit_code == execution.exit_code
        assert result.exception == execution.exception
        assert result.stdout == execution.stdout
        assert result.stderr == execution.stderr
        assert result.duration_ms == execution.duration_ms
        assert result.start_time is not None
        assert result.end_time is not None
