# tests/test_service/test_conditional_execution.py
"""Integration tests for conditional node execution."""

from datetime import datetime
from unittest.mock import Mock

from src.playbook.service.engine import RunbookEngine
from src.playbook.domain.models import (
    Runbook,
    RunInfo,
    NodeExecution,
    ManualNode,
    CommandNode,
    NodeType,
    NodeStatus,
    RunStatus,
    TriggerType,
)


class TestConditionalExecution:
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_clock = Mock()
        self.mock_clock.now.return_value = datetime(2025, 1, 1, 12, 0, 0)

        self.mock_process_runner = Mock()
        self.mock_run_repo = Mock()
        self.mock_node_repo = Mock()
        self.mock_io_handler = Mock()

        self.engine = RunbookEngine(
            clock=self.mock_clock,
            process_runner=self.mock_process_runner,
            run_repo=self.mock_run_repo,
            node_repo=self.mock_node_repo,
            io_handler=self.mock_io_handler,
        )

    def create_test_runbook_with_conditions(self):
        """Create a test runbook with conditional nodes."""
        nodes = {
            "build": ManualNode(
                id="build",
                type=NodeType.MANUAL,
                name="Build Application",
                depends_on=[],
                when="true",  # Always execute
            ),
            "test": CommandNode(
                id="test",
                type=NodeType.COMMAND,
                name="Run Tests",
                command_name="npm test",
                depends_on=["build"],
                when="{{ has_succeeded('build') }}",  # Only if build succeeded
            ),
            "deploy_staging": CommandNode(
                id="deploy_staging",
                type=NodeType.COMMAND,
                name="Deploy to Staging",
                command_name="deploy staging",
                depends_on=["test"],
                when="{{ has_succeeded('test') }}",  # Only if tests passed
            ),
            "deploy_production": CommandNode(
                id="deploy_production",
                type=NodeType.COMMAND,
                name="Deploy to Production",
                command_name="deploy production",
                depends_on=["deploy_staging"],
                when="{{ ENVIRONMENT == 'prod' and has_succeeded('deploy_staging') }}",
            ),
            "rollback": CommandNode(
                id="rollback",
                type=NodeType.COMMAND,
                name="Rollback Deployment",
                command_name="rollback",
                depends_on=["deploy_production"],
                when="{{ has_failed('deploy_production') }}",  # Only if production deploy failed
            ),
        }

        return Runbook(
            title="Conditional Deployment",
            description="Deployment with conditional branching",
            version="1.0.0",
            author="test",
            created_at=datetime.now(),
            nodes=nodes,
        )

    def test_should_execute_node_with_true_condition(self):
        """Test that node executes when condition is true."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing executions (build succeeded)
        build_execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )
        self.mock_node_repo.get_executions.return_value = [build_execution]

        # Test that 'test' node should execute (build succeeded)
        test_node = runbook.nodes["test"]
        should_execute = self.engine._should_execute_node(
            test_node, runbook, run_info, {}
        )
        assert should_execute is True

    def test_should_execute_node_with_false_condition(self):
        """Test that node doesn't execute when condition is false."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing executions (build failed)
        build_execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.NOK,
        )
        self.mock_node_repo.get_executions.return_value = [build_execution]

        # Test that 'test' node should not execute (build failed)
        test_node = runbook.nodes["test"]
        should_execute = self.engine._should_execute_node(
            test_node, runbook, run_info, {}
        )
        assert should_execute is False

    def test_should_execute_node_with_variable_condition(self):
        """Test condition evaluation with variables."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing executions (staging deploy succeeded)
        staging_execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy_staging",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )
        self.mock_node_repo.get_executions.return_value = [staging_execution]

        # Test with ENVIRONMENT = 'prod'
        prod_node = runbook.nodes["deploy_production"]
        should_execute = self.engine._should_execute_node(
            prod_node, runbook, run_info, {"ENVIRONMENT": "prod"}
        )
        assert should_execute is True

        # Test with ENVIRONMENT = 'dev'
        should_execute = self.engine._should_execute_node(
            prod_node, runbook, run_info, {"ENVIRONMENT": "dev"}
        )
        assert should_execute is False

    def test_execute_node_skipped_by_condition(self):
        """Test that node is skipped when condition is false."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing executions (build failed)
        build_execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.NOK,
        )
        self.mock_node_repo.get_executions.return_value = [build_execution]

        # Execute test node (should be skipped)
        status, execution = self.engine.execute_node(runbook, "test", run_info, {})

        assert status == NodeStatus.SKIPPED
        assert "condition" in execution.result_text.lower()
        self.mock_node_repo.create_execution.assert_called_once()

    def test_execute_node_condition_evaluates_true(self):
        """Test that node executes when condition evaluates to true."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing executions (build succeeded)
        build_execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )
        self.mock_node_repo.get_executions.return_value = [build_execution]

        # Mock successful command execution
        self.mock_process_runner.run_command.return_value = (0, "Tests passed", "")

        # Execute test node (should run because build succeeded)
        status, execution = self.engine.execute_node(runbook, "test", run_info, {})

        assert status == NodeStatus.OK
        self.mock_process_runner.run_command.assert_called_once_with(
            "npm test", 300, False
        )

    def test_validate_runbook_with_invalid_condition(self):
        """Test validation fails with invalid when condition."""
        nodes = {
            "test": CommandNode(
                id="test",
                type=NodeType.COMMAND,
                name="Test",
                command_name="test",
                depends_on=[],
                when="{{ invalid_syntax",  # Invalid Jinja2 syntax
            )
        }

        runbook = Runbook(
            title="Invalid Condition Test",
            description="Test",
            version="1.0.0",
            author="test",
            created_at=datetime.now(),
            nodes=nodes,
        )

        errors = self.engine.validate(runbook)
        assert len(errors) > 0
        assert any("Invalid 'when' condition" in error for error in errors)

    def test_condition_evaluation_error_defaults_to_execute(self):
        """Test that condition evaluation errors default to executing node."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock node_repo.get_executions to raise exception
        self.mock_node_repo.get_executions.side_effect = Exception("Database error")

        # Test should default to execute (fail-open)
        test_node = runbook.nodes["test"]
        should_execute = self.engine._should_execute_node(
            test_node, runbook, run_info, {}
        )
        assert should_execute is True

    def test_complex_conditional_workflow(self):
        """Test a complex workflow with multiple conditional branches."""
        runbook = self.create_test_runbook_with_conditions()
        run_info = RunInfo(
            workflow_name="test",
            run_id=1,
            start_time=datetime.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Simulate workflow execution: build succeeds, tests succeed, staging fails
        executions = [
            NodeExecution(
                workflow_name="test",
                run_id=1,
                node_id="build",
                attempt=1,
                start_time=datetime.now(),
                status=NodeStatus.OK,
            ),
            NodeExecution(
                workflow_name="test",
                run_id=1,
                node_id="test",
                attempt=1,
                start_time=datetime.now(),
                status=NodeStatus.OK,
            ),
            NodeExecution(
                workflow_name="test",
                run_id=1,
                node_id="deploy_staging",
                attempt=1,
                start_time=datetime.now(),
                status=NodeStatus.NOK,
            ),
        ]

        self.mock_node_repo.get_executions.return_value = executions

        # Test that production deploy should not execute (staging failed)
        prod_node = runbook.nodes["deploy_production"]
        should_execute = self.engine._should_execute_node(
            prod_node, runbook, run_info, {"ENVIRONMENT": "prod"}
        )
        assert should_execute is False

        # Test that rollback should not execute (production deploy didn't run)
        rollback_node = runbook.nodes["rollback"]
        should_execute = self.engine._should_execute_node(
            rollback_node, runbook, run_info, {}
        )
        assert should_execute is False
