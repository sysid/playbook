# src/playbook/service/engine.py
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from ..domain.models import (
    NodeType,
    NodeStatus,
    RunStatus,
    TriggerType,
    Runbook,
    RunInfo,
    NodeExecution,
    ManualNode,
    FunctionNode,
    CommandNode,
    BaseNode,
)
from ..domain.ports import (
    Clock,
    ProcessRunner,
    FunctionLoader,
    RunRepository,
    NodeExecutionRepository,
    NodeIOHandler,
)

logger = logging.getLogger(__name__)


class RunbookEngine:
    """Core engine for executing runbooks"""

    def __init__(
        self,
        clock: Clock,
        process_runner: ProcessRunner,
        function_loader: FunctionLoader,
        run_repo: RunRepository,
        node_repo: NodeExecutionRepository,
        io_handler: Optional[NodeIOHandler] = None,
    ):
        self.clock = clock
        self.process_runner = process_runner
        self.function_loader = function_loader
        self.run_repo = run_repo
        self.node_repo = node_repo
        self.io_handler = io_handler

    def validate(self, runbook: Runbook) -> List[str]:
        """Validate runbook for correctness"""
        errors = []

        # First check for references to non-existent nodes
        for node_id, node in runbook.nodes.items():
            for dep_id in node.depends_on:
                if dep_id not in runbook.nodes:
                    errors.append(
                        f"Node '{node_id}' depends on non-existent node '{dep_id}'"
                    )

        # Only check for cycles if all dependencies exist
        if not errors:
            # Check for cycles
            try:
                if self._has_cycles(runbook):
                    errors.append("Runbook contains cycles")
            except KeyError as e:
                # This shouldn't happen since we already checked for non-existent nodes
                errors.append(f"Reference to non-existent node: {e}")

        return errors

    def _has_cycles(self, runbook: Runbook) -> bool:
        """Check if runbook DAG has cycles"""
        visited = set()
        temp = set()

        def visit(node_id):
            if node_id in temp:
                return True
            if node_id in visited:
                return False

            temp.add(node_id)

            for dep in runbook.nodes[node_id].depends_on:
                if visit(dep):
                    return True

            temp.remove(node_id)
            visited.add(node_id)
            return False

        for node_id in runbook.nodes:
            if node_id not in visited:
                if visit(node_id):
                    return True

        return False

    def _get_execution_order(self, runbook: Runbook) -> List[str]:
        """Calculate topological sort of nodes"""
        visited = set()
        temp = set()
        order = []

        def visit(node_id):
            if node_id in temp:
                raise ValueError(f"Cycle detected at node '{node_id}'")
            if node_id in visited:
                return

            temp.add(node_id)

            for dep in runbook.nodes[node_id].depends_on:
                visit(dep)

            temp.remove(node_id)
            visited.add(node_id)
            order.append(node_id)

        for node_id in runbook.nodes:
            if node_id not in visited:
                visit(node_id)

        return order

    def start_run(self, runbook: Runbook) -> RunInfo:
        """Start a new runbook execution"""
        # Validate runbook
        errors = self.validate(runbook)
        if errors:
            raise ValueError(f"Runbook validation failed: {', '.join(errors)}")

        # Create run record
        run_info = RunInfo(
            workflow_name=runbook.title,
            run_id=0,  # Will be set by repository
            start_time=self.clock.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )

        run_id = self.run_repo.create_run(run_info)
        run_info.run_id = run_id

        return run_info

    def _handle_confirmation(self, node: BaseNode) -> bool:
        """Common handler for node confirmation if confirm is True"""
        if node.confirm and self.io_handler:
            approved = self.io_handler.handle_manual_prompt(
                node.id, node.name, node.description, node.prompt
            )
            return approved
        return True  # If confirmation not needed or no IO handler, proceed

    def resume_run(
        self, runbook: Runbook, run_id: int, start_node_id: Optional[str] = None
    ) -> RunInfo:
        """Resume a previously started run"""
        # Get existing run
        run_info = self.run_repo.get_run(runbook.title, run_id)

        # Verify run can be resumed (not OK or NOK)
        if run_info.status not in [RunStatus.RUNNING, RunStatus.ABORTED]:
            raise ValueError(f"Cannot resume run with status {run_info.status}")

        # Update run status
        run_info.status = RunStatus.RUNNING
        run_info.trigger = TriggerType.RESUME
        self.run_repo.update_run(run_info)

        return run_info

    def _execute_node_internal(
        self, node: BaseNode, start_time: Optional[datetime] = None
    ) -> NodeExecution:
        """Internal method for node execution logic"""
        if start_time is None:
            start_time = self.clock.now()

        try:
            # Execute based on node type
            if node.type == NodeType.MANUAL:
                result = self._execute_manual_node(node)
            elif node.type == NodeType.FUNCTION:
                result = self._execute_function_node(node)
            elif node.type == NodeType.COMMAND:
                result = self._execute_command_node(node)
            else:
                raise ValueError(f"Unknown node type: {node.type}")

            # Create execution record with results
            execution = NodeExecution(
                workflow_name="",  # Will be set by caller
                run_id=0,  # Will be set by caller
                node_id=node.id,
                attempt=1,  # Will be set by caller
                start_time=start_time,
                end_time=self.clock.now(),
                status=result.status,
                operator_decision=result.operator_decision,
                result_text=result.result_text,
                exit_code=result.exit_code,
                exception=result.exception,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=result.duration_ms,
            )

            return execution

        except Exception as e:
            # Handle exceptions
            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )

            return NodeExecution(
                workflow_name="",  # Will be set by caller
                run_id=0,  # Will be set by caller
                node_id=node.id,
                attempt=1,  # Will be set by caller
                start_time=start_time,
                end_time=end_time,
                status=NodeStatus.NOK,
                exception=str(e),
                duration_ms=duration_ms,
            )

    def resume_node_execution(
        self,
        runbook: Runbook,
        node_id: str,
        run_info: RunInfo,
        existing_execution: NodeExecution,
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Resume execution of a node that was already started"""
        node = runbook.nodes[node_id]

        # Update execution record to mark it as running again
        existing_execution.status = NodeStatus.RUNNING
        self.node_repo.update_execution(existing_execution)

        # Execute the node
        result = self._execute_node_internal(node, existing_execution.start_time)

        # Update execution record with result
        existing_execution.end_time = result.end_time
        existing_execution.status = result.status
        existing_execution.operator_decision = result.operator_decision
        existing_execution.result_text = result.result_text
        existing_execution.exit_code = result.exit_code
        existing_execution.exception = result.exception
        existing_execution.stdout = result.stdout
        existing_execution.stderr = result.stderr
        existing_execution.duration_ms = result.duration_ms

        self.node_repo.update_execution(existing_execution)

        return existing_execution.status, existing_execution

    def execute_node_with_existing_record(
        self, runbook: Runbook, node_id: str, run_info: RunInfo, attempt: int
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Execute a node while using an existing execution record"""
        node = runbook.nodes[node_id]
        start_time = self.clock.now()

        # Execute the node
        result = self._execute_node_internal(node, start_time)

        # Update with run information
        result.workflow_name = runbook.title
        result.run_id = run_info.run_id
        result.attempt = attempt

        # Update existing execution record
        self.node_repo.update_execution(result)

        return result.status, result

    def execute_node(
        self, runbook: Runbook, node_id: str, run_info: RunInfo
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Execute a single node"""
        node = runbook.nodes[node_id]
        start_time = self.clock.now()

        # Create initial execution record
        execution = NodeExecution(
            workflow_name=runbook.title,
            run_id=run_info.run_id,
            node_id=node_id,
            attempt=1,  # TODO: Handle retries
            start_time=start_time,
            status=NodeStatus.RUNNING,
        )

        self.node_repo.create_execution(execution)

        # Execute the node
        result = self._execute_node_internal(node, start_time)

        # Update execution record with result
        execution.end_time = result.end_time
        execution.status = result.status
        execution.operator_decision = result.operator_decision
        execution.result_text = result.result_text
        execution.exit_code = result.exit_code
        execution.exception = result.exception
        execution.stdout = result.stdout
        execution.stderr = result.stderr
        execution.duration_ms = result.duration_ms

        self.node_repo.update_execution(execution)

        return execution.status, execution

    def _execute_manual_node(self, node: ManualNode) -> NodeExecution:
        """Execute a manual node"""
        start_time = self.clock.now()
        execution = NodeExecution(
            workflow_name="",
            run_id=0,
            node_id="",
            attempt=0,
            start_time=start_time,
            status=NodeStatus.PENDING,
        )

        # For ManualNode, we always prompt
        if self.io_handler:
            approved = self.io_handler.handle_manual_prompt(
                node.id, node.name, node.description, node.prompt
            )
            execution.status = NodeStatus.OK if approved else NodeStatus.NOK
            execution.operator_decision = "approved" if approved else "rejected"
        else:
            # If no handler, leave as pending
            execution.status = NodeStatus.PENDING

        execution.end_time = self.clock.now()

        if execution.end_time and execution.start_time:
            execution.duration_ms = int(
                (execution.end_time - execution.start_time).total_seconds() * 1000
            )

        return execution

    def _execute_function_node(self, node: FunctionNode) -> NodeExecution:
        """Execute a function node"""
        start_time = self.clock.now()

        # Add confirmation check using the common handler
        if not self._handle_confirmation(node):
            return NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                end_time=self.clock.now(),
                status=NodeStatus.NOK,
                operator_decision="rejected",
            )

        try:
            result = self.function_loader.load_and_call(
                node.function_name, node.function_params
            )
            execution = NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                status=NodeStatus.OK,
                result_text=str(result),
            )

            # Use IO handler to display function result if available
            if self.io_handler and result:
                self.io_handler.handle_function_output(
                    node.id, node.name, node.description, str(result)
                )

            execution.end_time = self.clock.now()
            if execution.end_time and execution.start_time:
                execution.duration_ms = int(
                    (execution.end_time - execution.start_time).total_seconds() * 1000
                )

            return execution
        except Exception as e:
            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )

            return NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                end_time=end_time,
                status=NodeStatus.NOK,
                exception=str(e),
                duration_ms=duration_ms,
            )

    def _execute_command_node(self, node: CommandNode) -> NodeExecution:
        """Execute a shell command node"""
        start_time = self.clock.now()

        # Add confirmation check using the common handler
        if not self._handle_confirmation(node):
            return NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                end_time=self.clock.now(),
                status=NodeStatus.NOK,
                operator_decision="rejected",
            )

        try:
            exit_code, stdout, stderr = self.process_runner.run_command(
                node.command_name, node.timeout
            )

            status = NodeStatus.OK if exit_code == 0 else NodeStatus.NOK

            # If we have an IO handler, use it for output
            if self.io_handler and (stdout or stderr):
                self.io_handler.handle_command_output(
                    node.id, node.name, node.description, stdout, stderr
                )

            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )

            return NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                end_time=end_time,
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )
        except Exception as e:
            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )

            return NodeExecution(
                workflow_name="",
                run_id=0,
                node_id="",
                attempt=0,
                start_time=start_time,
                end_time=end_time,
                status=NodeStatus.NOK,
                exception=str(e),
                duration_ms=duration_ms,
            )

    def update_run_status(self, runbook: Runbook, run_info: RunInfo) -> RunStatus:
        """Update overall run status based on node executions"""
        executions = self.node_repo.get_executions(runbook.title, run_info.run_id)

        # Count node statuses
        nodes_ok = 0
        nodes_nok = 0
        nodes_skipped = 0

        for execution in executions:
            if execution.status == NodeStatus.OK:
                nodes_ok += 1
            elif execution.status == NodeStatus.NOK:
                nodes_nok += 1
            elif execution.status == NodeStatus.SKIPPED:
                nodes_skipped += 1

        run_info.nodes_ok = nodes_ok
        run_info.nodes_nok = nodes_nok
        run_info.nodes_skipped = nodes_skipped

        # Always update the node counts in the database
        self.run_repo.update_run(run_info)

        # Check for critical failures
        for execution in executions:
            node = runbook.nodes.get(execution.node_id)
            if node and node.critical and execution.status == NodeStatus.NOK:
                run_info.status = RunStatus.NOK
                run_info.end_time = self.clock.now()
                self.run_repo.update_run(run_info)
                return RunStatus.NOK

        # Check if all nodes are completed
        total_completed = nodes_ok + nodes_nok + nodes_skipped
        if total_completed == len(runbook.nodes):
            if nodes_nok > 0:
                run_info.status = RunStatus.NOK
            else:
                run_info.status = RunStatus.OK

            run_info.end_time = self.clock.now()
            self.run_repo.update_run(run_info)
            return run_info.status

        # Still running
        return RunStatus.RUNNING
