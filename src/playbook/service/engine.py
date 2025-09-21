# src/playbook/service/engine.py
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

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
    RunRepository,
    NodeExecutionRepository,
    NodeIOHandler,
)
from ..domain.plugins import (
    PluginNotFoundError,
    PluginExecutionError,
    FunctionNotFoundError,
)
from ..infrastructure.plugin_registry import plugin_registry
from ..infrastructure.conditions import ConditionEvaluator, ConditionContext

logger = logging.getLogger(__name__)


class RunbookEngine:
    """Core engine for executing runbooks"""

    def __init__(
        self,
        clock: Clock,
        process_runner: ProcessRunner,
        run_repo: RunRepository,
        node_repo: NodeExecutionRepository,
        io_handler: NodeIOHandler,
    ):
        self.clock = clock
        self.process_runner = process_runner
        self.run_repo = run_repo
        self.node_repo = node_repo
        self.io_handler = io_handler
        self.condition_evaluator = ConditionEvaluator()

        # Initialize plugin system
        self._initialize_plugins()

    def _initialize_plugins(self) -> None:
        """Initialize the plugin system."""
        try:
            plugin_registry.discover_plugins()

            # Register built-in Python plugin for backward compatibility
            from ..infrastructure.plugins.python_plugin import PythonPlugin

            plugin_registry.register_plugin("python", PythonPlugin)

            logger.debug(
                f"Plugin system initialized with {len(plugin_registry.list_plugins())} plugins"
            )
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")

    def validate(
        self, runbook: Runbook, variables: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Validate runbook for correctness"""
        errors = []

        # First check for references to non-existent nodes
        for node_id, node in runbook.nodes.items():
            for dep_id in node.depends_on:
                if dep_id not in runbook.nodes:
                    errors.append(
                        f"Node '{node_id}' depends on non-existent node '{dep_id}'"
                    )

        # Validate 'when' conditions
        for node_id, node in runbook.nodes.items():
            if hasattr(node, "when") and node.when and node.when != "true":
                try:
                    # Try to create a template to check syntax
                    from jinja2 import Environment, BaseLoader

                    env = Environment(loader=BaseLoader())
                    env.from_string(node.when)
                except Exception as e:
                    errors.append(f"Invalid 'when' condition in node '{node_id}': {e}")

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

    def _should_execute_node(
        self,
        node: BaseNode,
        runbook: Runbook,
        run_info: RunInfo,
        variables: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if a node should be executed based on its 'when' condition.

        Args:
            node: Node to check
            runbook: Current runbook
            run_info: Current run information
            variables: Workflow variables

        Returns:
            True if node should execute, False if it should be skipped
        """
        if variables is None:
            variables = {}

        # Default to execute if no condition or condition is "true"
        if not hasattr(node, "when") or node.when in ("true", "True", ""):
            return True

        try:
            # Get all existing executions for this run to build context
            executions = self.node_repo.get_executions(runbook.title, run_info.run_id)

            # Create execution map (use latest execution per node)
            execution_map = {}
            for execution in executions:
                node_id = execution.node_id
                if (
                    node_id not in execution_map
                    or execution.attempt > execution_map[node_id].attempt
                ):
                    execution_map[node_id] = execution

            # Create condition context
            context = ConditionContext(execution_map)

            # Evaluate the condition
            result = self.condition_evaluator.evaluate(node.when, variables, context)
            return result

        except Exception as e:
            logger.error(f"Error evaluating condition for node '{node.id}': {e}")
            # On error, default to execute (fail-open for safety)
            return True

    def _get_execution_order(self, runbook: Runbook) -> List[str]:
        """Calculate topological sort of nodes

        Time Complexity: O(V + E) where V is the number of nodes and E is the number of edges (dependencies)
        Space Complexity: O(V) for the sets and recursion stack
        Correctness: If a valid topological order exists (i.e., the graph is a DAG), this algorithm will find it
        """

        # objects are shared across all calls to visit, both direct and recursive
        # only one set of visited, temp, and order: shared state
        #  closures capture variables by reference, not by value: This means that the visit function doesn't just see
        #  the values at the time it was defined. It can see updates to these variables made by any call to visit
        visited = set()  # Nodes that have been fully processed
        temp = set()  # Nodes currently being processed (used for cycle detection)
        order = []  # Final topologically sorted list of nodes

        def visit(node_id):  # Inner function (closure)
            # Access to visited, temp, and order via closure
            # If node is in temp set, we've found a cycle (node depends on itself)
            if node_id in temp:
                raise ValueError(f"Cycle detected at node '{node_id}'")

            # If node is already visited, we've already processed this branch
            if node_id in visited:
                return

            # Mark node as "in progress" by adding to temp set
            temp.add(node_id)

            # Recursively visit all dependencies first
            for dep in runbook.nodes[node_id].depends_on:
                visit(dep)

            # Mark node as no longer in progress
            temp.remove(node_id)

            # Mark node as fully processed
            visited.add(node_id)

            # Add node to the result list (only after all its dependencies)
            order.append(node_id)

        # Visit all nodes to ensure we process all nodes, even disconnected ones
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

    def _handle_before_confirmation(self, node: BaseNode) -> bool:
        if node.prompt_before == "":
            raise ValueError("'prompt_before' message not defined")

        approved = self.io_handler.handle_prompt(node.id, node.name, node.prompt_before)
        return approved

    def _handle_after_confirmation(self, node: BaseNode) -> bool:
        if node.prompt_after == "":
            raise ValueError("'prompt_after' message not defined")

        approved = self.io_handler.handle_prompt(node.id, node.name, node.prompt_after)
        return approved

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
        variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Resume execution of a node that was already started"""
        node = runbook.nodes[node_id]

        if node.skip:
            if node.critical:
                raise ValueError(f"Node '{node_id}' is critical and cannot be skipped")
            # Update execution record to mark it as skipped
            existing_execution.status = NodeStatus.SKIPPED
            existing_execution.end_time = self.clock.now()
            existing_execution.result_text = (
                "Node skipped as configured in workflow definition"
            )
            self.node_repo.update_execution(existing_execution)

            # If there's an IO handler, inform about the skip
            if self.io_handler:
                self.io_handler.handle_description_output(
                    node_id, node.name, f"Skipped node: {node.description or ''}"
                )

            return existing_execution.status, existing_execution

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
        self,
        runbook: Runbook,
        node_id: str,
        run_info: RunInfo,
        attempt: int,
        variables: Optional[Dict[str, Any]] = None,
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

    def execute_node_retry(
        self,
        runbook: Runbook,
        node_id: str,
        run_info: RunInfo,
        attempt: int,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Execute a node retry, creating a new execution record with the specified attempt number"""
        node = runbook.nodes[node_id]
        start_time = self.clock.now()

        # Create a new execution record for this retry attempt
        execution = NodeExecution(
            workflow_name=runbook.title,
            run_id=run_info.run_id,
            node_id=node_id,
            attempt=attempt,
            start_time=start_time,
            status=NodeStatus.RUNNING,
        )

        # Create the new execution record in database
        self.node_repo.create_execution(execution)

        # Execute the node
        result = self._execute_node_internal(node, start_time)

        # Update execution record with result
        execution.end_time = result.end_time
        execution.status = result.status
        execution.result_text = result.result_text
        execution.exception = result.exception
        execution.stdout = result.stdout
        execution.stderr = result.stderr
        execution.exit_code = result.exit_code
        execution.duration_ms = result.duration_ms

        # Update the execution record with the results
        self.node_repo.update_execution(execution)

        return execution.status, execution

    def execute_node(
        self,
        runbook: Runbook,
        node_id: str,
        run_info: RunInfo,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[NodeStatus, NodeExecution]:
        """Execute a single node"""
        node = runbook.nodes[node_id]
        start_time = self.clock.now()

        if node.skip:
            if node.critical:
                raise ValueError(f"Node '{node_id}' is critical and cannot be skipped")
            execution = NodeExecution(
                workflow_name=runbook.title,
                run_id=run_info.run_id,
                node_id=node_id,
                attempt=1,
                start_time=start_time,
                end_time=self.clock.now(),  # End time is same as start for skipped nodes
                status=NodeStatus.SKIPPED,
                result_text="Node skipped as configured in workflow definition",
            )
            self.node_repo.create_execution(execution)

            self.io_handler.handle_description_output(
                node_id, node.name, f"Skipped node: {node.description or ''}"
            )

            return execution.status, execution

        # Check 'when' condition
        if not self._should_execute_node(node, runbook, run_info, variables):
            execution = NodeExecution(
                workflow_name=runbook.title,
                run_id=run_info.run_id,
                node_id=node_id,
                attempt=1,
                start_time=start_time,
                end_time=self.clock.now(),
                status=NodeStatus.SKIPPED,
                result_text=f"Node skipped due to condition: {node.when}",
            )
            self.node_repo.create_execution(execution)

            self.io_handler.handle_description_output(
                node_id,
                node.name,
                f"Skipped node (condition not met): {node.description or ''}",
            )

            return execution.status, execution

        # Create initial execution record
        execution = NodeExecution(
            workflow_name=runbook.title,
            run_id=run_info.run_id,
            node_id=node_id,
            attempt=1,
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

    def retry_node_execution(
        self, runbook: Runbook, node_id: str, run_info: RunInfo, max_attempts: int = 3
    ) -> Tuple[NodeStatus, NodeExecution, int]:
        """Retry execution of a failed node, creating new execution records for each attempt

        Returns:
            Tuple of (final_status, final_execution, total_attempts)
        """
        # Get the current latest attempt for this node
        latest_execution = self.node_repo.get_latest_execution_attempt(
            runbook.title, run_info.run_id, node_id
        )

        current_attempt = latest_execution.attempt if latest_execution else 0

        for attempt_number in range(current_attempt + 1, max_attempts + 1):
            logger.info(
                f"Retrying node '{node_id}' - attempt {attempt_number}/{max_attempts}"
            )

            # Execute node with new attempt number
            status, execution = self.execute_node_with_existing_record(
                runbook, node_id, run_info, attempt_number
            )

            if status == NodeStatus.OK:
                return status, execution, attempt_number

        # If we get here, all retry attempts failed
        # Return the last execution attempt
        final_execution = self.node_repo.get_latest_execution_attempt(
            runbook.title, run_info.run_id, node_id
        )
        return final_execution.status, final_execution, max_attempts

    def _execute_manual_node(self, node: ManualNode) -> NodeExecution:
        """Execute a manual node"""
        start_time = self.clock.now()
        execution = NodeExecution(
            workflow_name="",  # Will be set by caller
            run_id=0,  # Will be set by caller
            node_id="",  # Will be set by caller
            attempt=0,  # Will be set by caller
            start_time=start_time,
            status=NodeStatus.PENDING,
        )

        if node.prompt_before != "" and not self._handle_before_confirmation(node):
            execution.status = NodeStatus.NOK
            execution.operator_decision = "rejected"
            execution.end_time = self.clock.now()
            return execution

        self.io_handler.handle_description_output(node.id, node.name, node.description)

        if node.prompt_after == "":
            raise ValueError("Manual node must have a prompt_after message defined")

        if not self._handle_after_confirmation(node):
            execution.status = NodeStatus.NOK
            execution.operator_decision = "rejected"
            execution.end_time = self.clock.now()
            return execution

        end_time = self.clock.now()
        duration_ms = (
            int((end_time - start_time).total_seconds() * 1000)
            if end_time and start_time
            else None
        )
        execution.end_time = end_time
        execution.duration_ms = duration_ms
        execution.status = NodeStatus.OK
        execution.operator_decision = "approved"
        return execution

    def _execute_function_node(self, node: FunctionNode) -> NodeExecution:
        """Execute a function node"""
        start_time = self.clock.now()
        execution = NodeExecution(
            workflow_name="",  # Will be set by caller
            run_id=0,  # Will be set by caller
            node_id="",  # Will be set by caller
            attempt=0,  # Will be set by caller
            start_time=start_time,
            status=NodeStatus.PENDING,
        )

        if node.prompt_before != "" and not self._handle_before_confirmation(node):
            execution.status = NodeStatus.NOK
            execution.operator_decision = "rejected"
            execution.end_time = self.clock.now()
            return execution

        try:
            # Execute plugin-based function
            result = self._execute_plugin_function(node)
            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )
            execution.end_time = end_time
            execution.status = NodeStatus.OK
            execution.result_text = str(result)
            execution.duration_ms = duration_ms

            if self.io_handler and result:
                self.io_handler.handle_function_output(
                    node.id, node.name, node.description, str(result)
                )
            if node.prompt_after == "":  # No prompt_after confirmation
                return execution

            if not self._handle_after_confirmation(node):
                execution.status = NodeStatus.NOK
                execution.operator_decision = "rejected"
                execution.end_time = self.clock.now()
                return execution

            execution.operator_decision = "approved"
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

    def _execute_plugin_function(self, node: FunctionNode) -> Any:
        """Execute a plugin-based function.

        Args:
            node: FunctionNode with plugin and function specified

        Returns:
            Function execution result

        Raises:
            PluginNotFoundError: If plugin is not found
            PluginExecutionError: If function execution fails
        """
        try:
            # Get plugin configuration (merge global and node-specific)
            plugin_config = {}
            if node.plugin_config:
                plugin_config.update(node.plugin_config)

            # Get plugin instance
            plugin = plugin_registry.get_plugin(node.plugin, plugin_config)

            # Execute function with parameters
            result = plugin.execute(node.function, node.function_params)

            logger.debug(f"Successfully executed {node.plugin}.{node.function}")
            return result

        except (PluginNotFoundError, PluginExecutionError, FunctionNotFoundError):
            # Re-raise plugin-specific errors
            raise
        except Exception as e:
            # Wrap other exceptions
            raise PluginExecutionError(
                f"Unexpected error executing {node.plugin}.{node.function}: {e}"
            )

    def _execute_command_node(self, node: CommandNode) -> NodeExecution:
        """Execute a shell command node"""
        start_time = self.clock.now()
        execution = NodeExecution(
            workflow_name="",  # Will be set by caller
            run_id=0,  # Will be set by caller
            node_id="",  # Will be set by caller
            attempt=0,  # Will be set by caller
            start_time=start_time,
            status=NodeStatus.PENDING,
        )

        if node.prompt_before != "" and not self._handle_before_confirmation(node):
            execution.status = NodeStatus.NOK
            execution.operator_decision = "rejected"
            execution.end_time = self.clock.now()
            return execution

        try:
            exit_code, stdout, stderr = self.process_runner.run_command(
                node.command_name, node.timeout, node.interactive
            )
            end_time = self.clock.now()
            duration_ms = (
                int((end_time - start_time).total_seconds() * 1000)
                if end_time and start_time
                else None
            )
            execution.end_time = end_time
            execution.exit_code = exit_code
            execution.stdout = stdout
            execution.stderr = stderr
            execution.duration_ms = duration_ms

            # Determine node status based on exit code
            # Only show prompt_after if the command succeeded
            if exit_code == 0:
                execution.status = NodeStatus.OK

                # No output to display for interactive commands, since stdout/stderr were connected to terminal
                if not node.interactive and self.io_handler and (stdout or stderr):
                    self.io_handler.handle_command_output(
                        node.id, node.name, node.description, stdout, stderr
                    )

                # Only ask for prompt_after confirmation if the command succeeded
                if node.prompt_after != "":
                    if not self._handle_after_confirmation(node):
                        execution.status = NodeStatus.NOK
                        execution.operator_decision = "rejected"
                        execution.end_time = self.clock.now()
                        return execution
                    execution.operator_decision = "approved"
            else:
                # Command failed, mark as NOK without asking for confirmation
                execution.status = NodeStatus.NOK

                # Display stderr if available
                if self.io_handler and stderr:
                    self.io_handler.handle_command_output(
                        node.id, node.name, node.description, stdout, stderr
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

    def _get_latest_executions_per_node(
        self, executions: List[NodeExecution]
    ) -> Dict[str, NodeExecution]:
        """Get the latest execution attempt for each node.

        Args:
            executions: List of all executions for a run

        Returns:
            Dictionary mapping node_id to its latest execution
        """
        latest_executions = {}
        for execution in executions:
            node_id = execution.node_id
            if (
                node_id not in latest_executions
                or execution.attempt > latest_executions[node_id].attempt
            ):
                latest_executions[node_id] = execution
        return latest_executions

    def update_run_status(self, runbook: Runbook, run_info: RunInfo) -> RunStatus:
        """Update overall run status based on node executions"""
        executions = self.node_repo.get_executions(runbook.title, run_info.run_id)

        # Get only the latest execution attempt for each node
        latest_executions = self._get_latest_executions_per_node(executions)

        # Count node statuses based on latest attempts only
        nodes_ok = 0
        nodes_nok = 0
        nodes_skipped = 0

        for execution in latest_executions.values():
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

        # Check for critical failures (using latest executions only)
        for execution in latest_executions.values():
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

    def cleanup(self) -> None:
        """Clean up engine resources including plugins."""
        try:
            plugin_registry.cleanup_all()
            logger.debug("Engine cleanup completed")
        except Exception as e:
            logger.error(f"Error during engine cleanup: {e}")
