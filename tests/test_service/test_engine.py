# tests/service/test_engine.py
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from playbook.domain.models import (
    NodeType,
    NodeStatus,
    RunStatus,
    TriggerType,
    Runbook,
    RunInfo,
    NodeExecution,
    ManualNode,
)
from playbook.service.engine import RunbookEngine


class TestRunbookEngine:
    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for the engine"""
        clock = MagicMock()
        clock.now.return_value = datetime.now(timezone.utc)

        process_runner = MagicMock()
        function_loader = MagicMock()
        run_repo = MagicMock()
        node_repo = MagicMock()
        io_handler = MagicMock()

        return {
            "clock": clock,
            "process_runner": process_runner,
            "function_loader": function_loader,
            "run_repo": run_repo,
            "node_repo": node_repo,
            "io_handler": io_handler,
        }

    @pytest.fixture
    def engine(self, mock_dependencies):
        """Create RunbookEngine instance with mocked dependencies"""
        return RunbookEngine(
            clock=mock_dependencies["clock"],
            process_runner=mock_dependencies["process_runner"],
            function_loader=mock_dependencies["function_loader"],
            run_repo=mock_dependencies["run_repo"],
            node_repo=mock_dependencies["node_repo"],
            io_handler=mock_dependencies["io_handler"],
        )

    def test_has_cycles_whenNoCyclesExist_thenReturnsFalse(self, engine):
        """Test that _has_cycles correctly identifies acyclic graphs"""
        # Arrange - Create a simple linear workflow: A -> B -> C
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
                "C": ManualNode(
                    id="C",
                    type=NodeType.MANUAL,
                    prompt_after="Approve C?",
                    depends_on=["B"],
                ),
            },
        )

        # Act
        result = engine._has_cycles(runbook)

        # Assert
        assert result is False

    def test_has_cycles_whenCyclesExist_thenReturnsTrue(self, engine):
        """Test that _has_cycles correctly identifies cycles"""
        # Arrange - Create a workflow with a cycle: A -> B -> C -> A
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["C"],  # Creates a cycle
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
                "C": ManualNode(
                    id="C",
                    type=NodeType.MANUAL,
                    prompt_after="Approve C?",
                    depends_on=["B"],
                ),
            },
        )

        # Act
        result = engine._has_cycles(runbook)

        # Assert
        assert result is True

    def test_has_cycles_whenSelfLoop_thenReturnsTrue(self, engine):
        """Test that _has_cycles identifies a self-loop as a cycle"""
        # Arrange - Create a workflow with a self-loop: A -> A
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["A"],  # Self-loop
                )
            },
        )

        # Act
        result = engine._has_cycles(runbook)

        # Assert
        assert result is True

    def test_has_cycles_whenNonExistentDependency_thenRaisesKeyError(self, engine):
        """Test that _has_cycles raises KeyError for non-existent dependencies"""
        # Arrange - Create a workflow with non-existent dependency
        runbook = Runbook(
            title="Invalid Workflow",
            description="Invalid dependencies",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["Z"],  # Z doesn't exist
                )
            },
        )

        # Act & Assert
        with pytest.raises(KeyError, match="'Z'"):
            engine._has_cycles(runbook)

    def test_get_execution_order_whenLinearDependencies_thenCorrectOrder(self, engine):
        """Test that _get_execution_order returns correct order for linear dependencies"""
        # Arrange - Create a simple linear workflow: A -> B -> C
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
                "C": ManualNode(
                    id="C",
                    type=NodeType.MANUAL,
                    prompt_after="Approve C?",
                    depends_on=["B"],
                ),
            },
        )

        # Act
        result = engine._get_execution_order(runbook)

        # Assert
        assert result == ["A", "B", "C"]

    def test_get_execution_order_whenDiamondPattern_thenRespectsDependencies(
        self, engine
    ):
        """Test execution order for diamond pattern: A -> B, A -> C, B -> D, C -> D"""
        # Arrange
        runbook = Runbook(
            title="Diamond Workflow",
            description="Diamond-shaped dependency graph",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
                "C": ManualNode(
                    id="C",
                    type=NodeType.MANUAL,
                    prompt_after="Approve C?",
                    depends_on=["A"],
                ),
                "D": ManualNode(
                    id="D",
                    type=NodeType.MANUAL,
                    prompt_after="Approve D?",
                    depends_on=["B", "C"],
                ),
            },
        )

        # Act
        result = engine._get_execution_order(runbook)

        # Assert
        # A must come before B and C, and B and C must come before D
        assert result.index("A") < result.index("B")
        assert result.index("A") < result.index("C")
        assert result.index("B") < result.index("D")
        assert result.index("C") < result.index("D")

    def test_get_execution_order_whenComplexDAG_thenTopologicalSort(self, engine):
        """Test execution order for a more complex DAG"""
        # Arrange
        runbook = Runbook(
            title="Complex DAG",
            description="Complex dependencies",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
                "C": ManualNode(
                    id="C",
                    type=NodeType.MANUAL,
                    prompt_after="Approve C?",
                    depends_on=["A"],
                ),
                "D": ManualNode(
                    id="D",
                    type=NodeType.MANUAL,
                    prompt_after="Approve D?",
                    depends_on=["B", "C"],
                ),
                "E": ManualNode(
                    id="E",
                    type=NodeType.MANUAL,
                    prompt_after="Approve E?",
                    depends_on=["B"],
                ),
                "F": ManualNode(
                    id="F",
                    type=NodeType.MANUAL,
                    prompt_after="Approve F?",
                    depends_on=["C", "E"],
                ),
            },
        )

        # Act
        result = engine._get_execution_order(runbook)

        # Assert - Check all dependency relationships are satisfied
        assert result.index("A") < result.index("B")
        assert result.index("A") < result.index("C")
        assert result.index("B") < result.index("D")
        assert result.index("C") < result.index("D")
        assert result.index("B") < result.index("E")
        assert result.index("C") < result.index("F")
        assert result.index("E") < result.index("F")

    def test_get_execution_order_whenCycleExists_thenRaisesValueError(self, engine):
        """Test that _get_execution_order raises a ValueError when a cycle is detected"""
        # Arrange - Create a workflow with a cycle: A -> B -> A
        runbook = Runbook(
            title="Cyclic Workflow",
            description="Contains a cycle",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["B"],  # Creates a cycle
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Cycle detected"):
            engine._get_execution_order(runbook)

    def test_get_execution_order_whenNonExistentDependency_thenRaisesKeyError(
        self, engine
    ):
        """Test that _get_execution_order raises KeyError for non-existent dependencies"""
        # Arrange - Create a workflow with non-existent dependency
        runbook = Runbook(
            title="Invalid Workflow",
            description="Invalid dependencies",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["Z"],  # Z doesn't exist
                )
            },
        )

        # Act & Assert
        with pytest.raises(KeyError, match="'Z'"):
            engine._get_execution_order(runbook)

    def test_validate_whenValidRunbook_thenNoErrors(self, engine):
        """Test validation for a valid runbook"""
        # Arrange
        runbook = Runbook(
            title="Valid Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        # Act
        errors = engine.validate(runbook)

        # Assert
        assert errors == []

    def test_validate_whenCycleExists_thenReturnsError(self, engine):
        """Test validation catches cycles"""
        # Arrange
        runbook = Runbook(
            title="Cyclic Workflow",
            description="Contains a cycle",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["B"],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        # Act
        errors = engine.validate(runbook)

        # Assert
        assert len(errors) == 1
        assert "cycles" in errors[0].lower()

    def test_validate_whenNonExistentDependency_thenReturnsError(self, engine):
        """Test validation catches references to non-existent nodes"""
        # Arrange
        runbook = Runbook(
            title="Invalid Dependencies",
            description="Contains non-existent dependency",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["Z"],  # Z doesn't exist
                ),
            },
        )

        # Act
        errors = engine.validate(runbook)

        # Assert
        assert len(errors) == 1
        assert "non-existent node" in errors[0]
        assert "'Z'" in errors[0]

    def test_start_run_whenValidRunbook_thenRunCreated(self, engine, mock_dependencies):
        """Test that start_run creates a run with proper initialization"""
        # Arrange
        mock_dependencies["run_repo"].create_run.return_value = 123  # Run ID

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                )
            },
        )

        # Act
        run_info = engine.start_run(runbook)

        # Assert
        assert run_info.workflow_name == "Test Workflow"
        assert run_info.run_id == 123
        assert run_info.status == RunStatus.RUNNING
        assert run_info.trigger == TriggerType.RUN
        mock_dependencies["run_repo"].create_run.assert_called_once()

    def test_start_run_whenInvalidRunbook_thenRaisesValueError(self, engine):
        """Test that start_run validates the runbook"""
        # Arrange
        # Create a runbook with a cycle
        runbook = Runbook(
            title="Cyclic Workflow",
            description="Contains a cycle",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=["B"],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        # Act & Assert
        with pytest.raises(ValueError, match="validation failed"):
            engine.start_run(runbook)

    def test_update_run_status_whenAllNodesOK_thenRunStatusOK(
        self, engine, mock_dependencies
    ):
        """Test that update_run_status sets OK status when all nodes are OK"""
        # Arrange
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Two successful node executions
        mock_dependencies["node_repo"].get_executions.return_value = [
            NodeExecution(
                workflow_name="Test Workflow",
                run_id=123,
                node_id="A",
                attempt=1,
                start_time=datetime.now(timezone.utc),
                status=NodeStatus.OK,
            ),
            NodeExecution(
                workflow_name="Test Workflow",
                run_id=123,
                node_id="B",
                attempt=1,
                start_time=datetime.now(timezone.utc),
                status=NodeStatus.OK,
            ),
        ]

        # Act
        result = engine.update_run_status(runbook, run_info)

        # Assert
        assert result == RunStatus.OK
        assert run_info.status == RunStatus.OK
        assert run_info.nodes_ok == 2
        assert run_info.nodes_nok == 0
        assert run_info.end_time is not None
        # Check that update_run was called exactly twice
        assert mock_dependencies["run_repo"].update_run.call_count == 2

    def test_update_run_status_whenCriticalNodeFails_thenRunStatusNOK(
        self, engine, mock_dependencies
    ):
        """Test that update_run_status sets NOK status when a critical node fails"""
        # Arrange
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                    critical=True,  # Critical node
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Node A fails (critical node)
        mock_dependencies["node_repo"].get_executions.return_value = [
            NodeExecution(
                workflow_name="Test Workflow",
                run_id=123,
                node_id="A",
                attempt=1,
                start_time=datetime.now(timezone.utc),
                status=NodeStatus.NOK,  # Failed node
            )
        ]

        # Act
        result = engine.update_run_status(runbook, run_info)

        # Assert
        assert result == RunStatus.NOK
        assert run_info.status == RunStatus.NOK
        assert run_info.nodes_ok == 0
        assert run_info.nodes_nok == 1
        assert run_info.end_time is not None
        # Check that update_run was called exactly twice
        assert mock_dependencies["run_repo"].update_run.call_count == 2

    def test_update_run_status_whenNonCriticalNodeFails_thenContinuesRunning(
        self, engine, mock_dependencies
    ):
        """Test that update_run_status allows run to continue when non-critical nodes fail"""
        # Arrange
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                    critical=False,  # Non-critical node
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Node A fails (non-critical node), B not yet executed
        mock_dependencies["node_repo"].get_executions.return_value = [
            NodeExecution(
                workflow_name="Test Workflow",
                run_id=123,
                node_id="A",
                attempt=1,
                start_time=datetime.now(timezone.utc),
                status=NodeStatus.NOK,  # Failed node
            )
        ]

        # Act
        result = engine.update_run_status(runbook, run_info)

        # Assert
        assert result == RunStatus.RUNNING  # Still running
        assert run_info.status == RunStatus.RUNNING
        assert run_info.nodes_ok == 0
        assert run_info.nodes_nok == 1
        assert run_info.end_time is None  # Not finished yet

    def test_resume_run_whenRunExists_thenRunResumed(self, engine, mock_dependencies):
        """Test that resume_run properly resumes an existing run"""
        # Arrange
        existing_run = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.ABORTED,  # Previous run was aborted
            trigger=TriggerType.RUN,
            nodes_ok=1,
            nodes_nok=1,
        )

        mock_dependencies["run_repo"].get_run.return_value = existing_run

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "A": ManualNode(
                    id="A",
                    type=NodeType.MANUAL,
                    prompt_after="Approve A?",
                    depends_on=[],
                ),
                "B": ManualNode(
                    id="B",
                    type=NodeType.MANUAL,
                    prompt_after="Approve B?",
                    depends_on=["A"],
                ),
            },
        )

        # Act
        resumed_run = engine.resume_run(runbook, 123)

        # Assert
        assert resumed_run.workflow_name == "Test Workflow"
        assert resumed_run.run_id == 123
        assert resumed_run.status == RunStatus.RUNNING
        assert resumed_run.trigger == TriggerType.RESUME
        mock_dependencies["run_repo"].get_run.assert_called_once_with(
            "Test Workflow", 123
        )
        mock_dependencies["run_repo"].update_run.assert_called_once()

    def test_resume_run_whenRunStatusNotResumable_thenRaisesValueError(
        self, engine, mock_dependencies
    ):
        """Test that resume_run validates run status before resuming"""
        # Arrange
        existing_run = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.OK,  # Completed run - can't resume
            trigger=TriggerType.RUN,
        )

        mock_dependencies["run_repo"].get_run.return_value = existing_run

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={},
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot resume run with status"):
            engine.resume_run(runbook, 123)

    def test_resume_node_execution_whenManualNode_thenExecutesManualNode(
        self, engine, mock_dependencies
    ):
        """Test that resume_node_execution correctly handles manual nodes"""
        # Arrange
        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "manual_node": ManualNode(
                    id="manual_node",
                    type=NodeType.MANUAL,
                    prompt_after="Approve?",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="manual_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.PENDING,
        )

        # Mock the IO handler to approve the manual node
        mock_dependencies["io_handler"].handle_prompt.return_value = True

        # Act
        status, updated_execution = engine.resume_node_execution(
            runbook, "manual_node", run_info, existing_execution
        )

        # Assert
        assert status == NodeStatus.OK
        assert updated_execution.status == NodeStatus.OK
        assert updated_execution.operator_decision == "approved"
        assert updated_execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called()
        assert mock_dependencies["io_handler"].handle_prompt.call_count == 1

    def test_resume_node_execution_whenFunctionNode_thenExecutesFunction(
        self, engine, mock_dependencies
    ):
        """Test that resume_node_execution correctly handles function nodes"""
        # Arrange - Create a function node
        from playbook.domain.models import FunctionNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "func_node": FunctionNode(
                    id="func_node",
                    type=NodeType.FUNCTION,
                    function_name="test_function",
                    function_params={"param1": "value1"},
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="func_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.RUNNING,
        )

        # Mock function loader to return a result
        mock_dependencies[
            "function_loader"
        ].load_and_call.return_value = "Function result"

        # Act
        status, updated_execution = engine.resume_node_execution(
            runbook, "func_node", run_info, existing_execution
        )

        # Assert
        assert status == NodeStatus.OK
        assert updated_execution.status == NodeStatus.OK
        assert updated_execution.result_text == "Function result"
        assert updated_execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called()
        mock_dependencies["function_loader"].load_and_call.assert_called_once_with(
            "test_function", {"param1": "value1"}
        )

    def test_resume_node_execution_whenCommandNode_thenExecutesCommand(
        self, engine, mock_dependencies
    ):
        """Test that resume_node_execution correctly handles command nodes"""
        # Arrange - Create a command node
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "cmd_node": CommandNode(
                    id="cmd_node",
                    type=NodeType.COMMAND,
                    command_name="echo test",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="cmd_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.RUNNING,
        )

        # Mock process runner
        mock_dependencies["process_runner"].run_command.return_value = (
            0,
            "Command output",
            "",
        )

        # Act
        status, updated_execution = engine.resume_node_execution(
            runbook, "cmd_node", run_info, existing_execution
        )

        # Assert
        assert status == NodeStatus.OK
        assert updated_execution.status == NodeStatus.OK
        assert updated_execution.exit_code == 0
        assert updated_execution.stdout == "Command output"
        assert updated_execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called()
        mock_dependencies["process_runner"].run_command.assert_called_once()

    def test_resume_node_execution_whenFunctionRaisesException_thenNodeNOK(
        self, engine, mock_dependencies
    ):
        """Test that resume_node_execution handles exceptions during execution"""
        # Arrange - Create a function node
        from playbook.domain.models import FunctionNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "func_node": FunctionNode(
                    id="func_node",
                    type=NodeType.FUNCTION,
                    function_name="test_function",
                    function_params={"param1": "value1"},
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="func_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.RUNNING,
        )

        # Mock function loader to raise an exception
        test_exception = RuntimeError("Test function error")
        mock_dependencies["function_loader"].load_and_call.side_effect = test_exception

        # Act
        status, updated_execution = engine.resume_node_execution(
            runbook, "func_node", run_info, existing_execution
        )

        # Assert
        assert status == NodeStatus.NOK
        assert updated_execution.status == NodeStatus.NOK
        assert updated_execution.exception == str(test_exception)
        assert updated_execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called()

    def test_execute_node_with_existing_record_whenSuccessful_thenUpdatesExecution(
        self, engine, mock_dependencies
    ):
        """Test that execute_node_with_existing_record updates execution records"""
        # Arrange
        from playbook.domain.models import FunctionNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "func_node": FunctionNode(
                    id="func_node",
                    type=NodeType.FUNCTION,
                    function_name="test_function",
                    function_params={"param1": "value1"},
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        # Mock function loader to return a result
        mock_dependencies[
            "function_loader"
        ].load_and_call.return_value = "Function result"

        # Act
        status, execution = engine.execute_node_with_existing_record(
            runbook,
            "func_node",
            run_info,
            2,  # attempt 2
        )

        # Assert
        assert status == NodeStatus.OK
        assert execution.status == NodeStatus.OK
        assert execution.result_text == "Function result"
        assert execution.attempt == 2
        assert execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called_once()
        mock_dependencies["function_loader"].load_and_call.assert_called_once()

    def test_execute_node_with_existing_record_whenException_thenHandlesError(
        self, engine, mock_dependencies
    ):
        """Test that execute_node_with_existing_record handles exceptions"""
        # Arrange
        from playbook.domain.models import FunctionNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "func_node": FunctionNode(
                    id="func_node",
                    type=NodeType.FUNCTION,
                    function_name="test_function",
                    function_params={"param1": "value1"},
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RESUME,
        )

        # Mock function loader to raise an exception
        test_exception = RuntimeError("Test function error")
        mock_dependencies["function_loader"].load_and_call.side_effect = test_exception

        # Act
        status, execution = engine.execute_node_with_existing_record(
            runbook,
            "func_node",
            run_info,
            2,  # attempt 2
        )

        # Assert
        assert status == NodeStatus.NOK
        assert execution.status == NodeStatus.NOK
        assert execution.exception == str(test_exception)
        assert execution.attempt == 2
        assert execution.end_time is not None
        mock_dependencies["node_repo"].update_execution.assert_called_once()

    def test_retry_node_execution_when_successful_retry_then_returns_success(self, engine, mock_dependencies):
        """Test that retry_node_execution handles successful retry"""
        # Arrange
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "test_node": CommandNode(
                    id="test_node",
                    type=NodeType.COMMAND,
                    command_name="test command",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing execution (attempt 1 failed)
        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="test_node",
            attempt=1,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.NOK,
        )
        mock_dependencies["node_repo"].get_latest_execution_attempt.return_value = existing_execution

        # Mock successful retry (attempt 2)
        mock_dependencies["process_runner"].run_command.return_value = (0, "Success", "")

        # Act
        status, execution, final_attempt = engine.retry_node_execution(
            runbook, "test_node", run_info, max_attempts=3
        )

        # Assert
        assert status == NodeStatus.OK
        assert final_attempt == 2
        assert execution.attempt == 2
        assert execution.status == NodeStatus.OK
        mock_dependencies["node_repo"].get_latest_execution_attempt.assert_called_once()

    def test_retry_node_execution_when_max_attempts_reached_then_returns_failure(self, engine, mock_dependencies):
        """Test that retry_node_execution handles max attempts reached"""
        # Arrange
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "test_node": CommandNode(
                    id="test_node",
                    type=NodeType.COMMAND,
                    command_name="failing command",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock existing execution (attempt 2 failed)
        existing_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="test_node",
            attempt=2,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.NOK,
        )

        # Final execution after all retries failed
        final_execution = NodeExecution(
            workflow_name="Test Workflow",
            run_id=123,
            node_id="test_node",
            attempt=3,
            start_time=datetime.now(timezone.utc),
            status=NodeStatus.NOK,
        )

        mock_dependencies["node_repo"].get_latest_execution_attempt.side_effect = [
            existing_execution,  # First call
            final_execution      # Second call (after retry)
        ]

        # Mock failing command
        mock_dependencies["process_runner"].run_command.return_value = (1, "", "Command failed")

        # Act
        status, execution, final_attempt = engine.retry_node_execution(
            runbook, "test_node", run_info, max_attempts=3
        )

        # Assert
        assert status == NodeStatus.NOK
        assert final_attempt == 3
        assert execution.attempt == 3
        assert execution.status == NodeStatus.NOK

    def test_retry_node_execution_when_no_existing_execution_then_starts_from_attempt_one(self, engine, mock_dependencies):
        """Test that retry_node_execution starts from attempt 1 when no existing execution"""
        # Arrange
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "test_node": CommandNode(
                    id="test_node",
                    type=NodeType.COMMAND,
                    command_name="test command",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock no existing execution
        mock_dependencies["node_repo"].get_latest_execution_attempt.return_value = None

        # Mock successful execution on first retry attempt
        mock_dependencies["process_runner"].run_command.return_value = (0, "Success", "")

        # Act
        status, execution, final_attempt = engine.retry_node_execution(
            runbook, "test_node", run_info, max_attempts=3
        )

        # Assert
        assert status == NodeStatus.OK
        assert final_attempt == 1  # Started from attempt 1
        assert execution.attempt == 1

    def test_execute_node_with_existing_record_when_given_attempt_number_then_creates_correct_execution(self, engine, mock_dependencies):
        """Test that execute_node_with_existing_record creates execution with correct attempt number"""
        # Arrange
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "test_node": CommandNode(
                    id="test_node",
                    type=NodeType.COMMAND,
                    command_name="test command",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock successful command execution
        mock_dependencies["process_runner"].run_command.return_value = (0, "Test output", "")

        # Act - Execute with attempt number 5
        status, execution = engine.execute_node_with_existing_record(
            runbook, "test_node", run_info, attempt=5
        )

        # Assert
        assert status == NodeStatus.OK
        assert execution.attempt == 5
        assert execution.workflow_name == "Test Workflow"
        assert execution.run_id == 123
        assert execution.node_id == "test_node"
        assert execution.stdout == "Test output"
        mock_dependencies["node_repo"].update_execution.assert_called_once()

    def test_execute_node_with_existing_record_when_command_fails_then_handles_error(self, engine, mock_dependencies):
        """Test that execute_node_with_existing_record handles command failures correctly"""
        # Arrange
        from playbook.domain.models import CommandNode

        runbook = Runbook(
            title="Test Workflow",
            description="Test Description",
            version="1.0",
            author="Test Author",
            created_at=datetime.now(timezone.utc),
            nodes={
                "test_node": CommandNode(
                    id="test_node",
                    type=NodeType.COMMAND,
                    command_name="failing command",
                    depends_on=[],
                )
            },
        )

        run_info = RunInfo(
            workflow_name="Test Workflow",
            run_id=123,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        # Mock failing command execution
        mock_dependencies["process_runner"].run_command.return_value = (1, "", "Command failed")

        # Act
        status, execution = engine.execute_node_with_existing_record(
            runbook, "test_node", run_info, attempt=2
        )

        # Assert
        assert status == NodeStatus.NOK
        assert execution.attempt == 2
        assert execution.status == NodeStatus.NOK
        assert execution.exit_code == 1
        assert execution.stderr == "Command failed"
        mock_dependencies["node_repo"].update_execution.assert_called_once()
