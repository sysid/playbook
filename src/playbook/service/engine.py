from __future__ import annotations

from typing import Any

from ..domain.models import (
    CommandStep,
    FunctionStep,
    ManualStep,
    NodeExecution,
    NodeStatus,
    Runbook,
    RunInfo,
    RunStatus,
    Step,
    TriggerType,
)
from ..domain.ports import (
    Clock,
    NodeExecutionRepository,
    NodeIOHandler,
    ProcessRunner,
    RunRepository,
)
from ..infrastructure.plugin_registry import PluginRegistry, plugin_registry
from ..infrastructure.redaction import Redactor


class RunbookEngine:
    """Execute an ordered runbook as a guided operator interaction."""

    def __init__(
        self,
        clock: Clock,
        process_runner: ProcessRunner,
        run_repo: RunRepository,
        node_repo: NodeExecutionRepository,
        io_handler: NodeIOHandler,
        plugins: PluginRegistry | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.clock = clock
        self.process_runner = process_runner
        self.run_repo = run_repo
        self.node_repo = node_repo
        self.io_handler = io_handler
        self.plugins = plugins or plugin_registry
        self.max_attempts = max_attempts
        self.redactor = Redactor()
        self._register_builtin_plugin()

    def _register_builtin_plugin(self) -> None:
        from ..infrastructure.plugins.python_plugin import PythonPlugin

        self.plugins.register_plugin("python", PythonPlugin)

    def run(self, runbook: Runbook) -> RunInfo:
        self._configure_redaction(runbook)
        run_info = RunInfo(
            workflow_name=runbook.id,
            run_id=0,
            start_time=self.clock.now(),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
            source_path=runbook.source_path,
            definition_hash=runbook.definition_hash,
            variables=self._persistable_variables(runbook),
        )
        run_info.run_id = self.run_repo.create_run(run_info)
        return self._run_with_interrupt_handling(runbook, run_info, {})

    def resume(self, runbook: Runbook, run_id: int) -> RunInfo:
        self._configure_redaction(runbook)
        run_info = self.run_repo.get_run(runbook.id, run_id)
        if run_info.definition_hash != runbook.definition_hash:
            raise ValueError(
                "The workflow definition has changed since this run started; "
                "start a new run instead"
            )
        if run_info.status not in (RunStatus.ABORTED, RunStatus.RUNNING):
            raise ValueError(
                f"Run {runbook.id}/{run_id} is {run_info.status.value} and cannot be resumed"
            )
        current_variables = self._persistable_variables(runbook)
        if run_info.variables != current_variables:
            raise ValueError(
                "The workflow variable values have changed since this run started; "
                "use the original values or start a new run"
            )
        latest: dict[str, NodeExecution] = {}
        for execution in self.node_repo.get_executions(runbook.id, run_id):
            current = latest.get(execution.node_id)
            if current is None or execution.attempt > current.attempt:
                latest[execution.node_id] = execution
        self._ensure_resume_attempt_available(runbook, latest)
        run_info.status = RunStatus.RUNNING
        run_info.trigger = TriggerType.RESUME
        run_info.end_time = None
        run_info.variables = current_variables
        self.run_repo.update_run(run_info)
        return self._run_with_interrupt_handling(runbook, run_info, latest)

    @staticmethod
    def _persistable_variables(runbook: Runbook) -> dict[str, Any]:
        return {
            name: value
            for name, value in runbook.variables.items()
            if not runbook.variable_definitions.get(name)
            or not runbook.variable_definitions[name].secret
        }

    def _ensure_resume_attempt_available(
        self,
        runbook: Runbook,
        latest: dict[str, NodeExecution],
    ) -> None:
        completed = (NodeStatus.OK, NodeStatus.SKIPPED, NodeStatus.DISABLED)
        for step in runbook.steps:
            prior = latest.get(step.id)
            if prior and prior.status in completed:
                continue
            if (
                isinstance(step, (CommandStep, FunctionStep))
                and prior
                and prior.attempt >= self.max_attempts
            ):
                raise ValueError(
                    f"Step '{step.id}' exhausted {self.max_attempts} attempts; "
                    "increase --max-attempts to resume it"
                )
            return

    def _run_with_interrupt_handling(
        self,
        runbook: Runbook,
        run_info: RunInfo,
        previous: dict[str, NodeExecution],
    ) -> RunInfo:
        try:
            return self._run_steps(runbook, run_info, previous)
        except KeyboardInterrupt:
            run_info.status = RunStatus.ABORTED
            run_info.end_time = self.clock.now()
            self.run_repo.update_run(run_info)
            raise

    def _run_steps(
        self,
        runbook: Runbook,
        run_info: RunInfo,
        previous: dict[str, NodeExecution],
    ) -> RunInfo:
        for position, step in enumerate(runbook.steps, start=1):
            prior = previous.get(step.id)
            if prior and prior.status in (
                NodeStatus.OK,
                NodeStatus.SKIPPED,
                NodeStatus.DISABLED,
            ):
                continue
            if prior and prior.status == NodeStatus.RUNNING:
                prior.status = NodeStatus.ABORTED
                prior.operator_decision = "stale-run-takeover"
                prior.end_time = self.clock.now()
                self.node_repo.update_execution(prior)
            outcome = self._guide_step(
                runbook,
                run_info,
                step,
                position,
                len(runbook.steps),
                prior.attempt + 1 if prior else 1,
            )
            self._count(outcome, run_info)
            if outcome.status == NodeStatus.ABORTED:
                run_info.status = RunStatus.ABORTED
                run_info.end_time = self.clock.now()
                self.run_repo.update_run(run_info)
                return run_info
            self.run_repo.update_run(run_info)

        run_info.status = RunStatus.OK
        run_info.end_time = self.clock.now()
        self.run_repo.update_run(run_info)
        return run_info

    def _configure_redaction(self, runbook: Runbook) -> None:
        self.redactor = Redactor(
            value
            for name, value in runbook.variables.items()
            if runbook.variable_definitions.get(name)
            and runbook.variable_definitions[name].secret
        )

    def _guide_step(
        self,
        runbook: Runbook,
        run_info: RunInfo,
        step: Step,
        position: int,
        total: int,
        attempt: int,
    ) -> NodeExecution:
        if not step.enabled or (
            step.enabled_if is not None and not bool(runbook.variables[step.enabled_if])
        ):
            return self._record_without_execution(
                runbook.id,
                run_info.run_id,
                step.id,
                NodeStatus.DISABLED,
                "disabled",
                attempt,
            )

        self.io_handler.show_step(
            runbook,
            self._redacted_step(step),
            position,
            total,
        )
        if isinstance(step, ManualStep):
            choices = ("done", "abort") if step.required else ("done", "skip", "abort")
            action = self.io_handler.choose(step.prompt, choices)
            return self._record_operator_action(
                runbook, run_info, step, action, attempt
            )

        choices = ("run", "abort") if step.required else ("run", "skip", "abort")
        action = self.io_handler.choose("Run this step?", choices)
        if action != "run":
            return self._record_operator_action(
                runbook, run_info, step, action, attempt
            )
        return self._execute_until_resolved(runbook, run_info, step, attempt)

    def _record_operator_action(
        self,
        runbook: Runbook,
        run_info: RunInfo,
        step: Step,
        action: str,
        attempt: int,
    ) -> NodeExecution:
        status = {
            "done": NodeStatus.OK,
            "skip": NodeStatus.SKIPPED,
            "abort": NodeStatus.ABORTED,
        }[action]
        return self._record_without_execution(
            runbook.id,
            run_info.run_id,
            step.id,
            status,
            action,
            attempt,
        )

    def _execute_until_resolved(
        self,
        runbook: Runbook,
        run_info: RunInfo,
        step: CommandStep | FunctionStep,
        first_attempt: int,
    ) -> NodeExecution:
        attempt = first_attempt
        while True:
            execution = self._execute_once(runbook.id, run_info.run_id, step, attempt)
            if execution.status == NodeStatus.OK:
                verify = step.verify
                if not verify:
                    return execution
                choices = (
                    ("done", "retry", "abort")
                    if attempt < self.max_attempts
                    else ("done", "abort")
                )
                action = self.io_handler.choose(verify, choices)
                if action == "done":
                    return execution
                if action == "abort":
                    execution.status = NodeStatus.ABORTED
                    execution.operator_decision = "abort"
                    self.node_repo.update_execution(execution)
                    return execution
                attempt += 1
                continue

            if attempt >= self.max_attempts:
                execution.status = NodeStatus.ABORTED
                execution.operator_decision = "retry-limit"
                self.node_repo.update_execution(execution)
                return execution
            choices = (
                ("retry", "abort") if step.required else ("retry", "skip", "abort")
            )
            action = self.io_handler.choose("Step failed.", choices)
            if action == "retry":
                attempt += 1
                continue
            execution.status = (
                NodeStatus.SKIPPED if action == "skip" else NodeStatus.ABORTED
            )
            execution.operator_decision = action
            self.node_repo.update_execution(execution)
            return execution

    def _execute_once(
        self,
        workflow_id: str,
        run_id: int,
        step: CommandStep | FunctionStep,
        attempt: int,
    ) -> NodeExecution:
        execution = NodeExecution(
            workflow_name=workflow_id,
            run_id=run_id,
            node_id=step.id,
            attempt=attempt,
            start_time=self.clock.now(),
            status=NodeStatus.RUNNING,
        )
        try:
            if isinstance(step, CommandStep):
                exit_code, stdout, stderr = self.process_runner.run_command(
                    step.command,
                    step.timeout_seconds,
                    step.interactive,
                )
                execution.exit_code = exit_code
                execution.stdout = self.redactor.redact(stdout)
                execution.stderr = self.redactor.redact(stderr)
                execution.result_text = self.redactor.redact(stdout)
                execution.status = NodeStatus.OK if exit_code == 0 else NodeStatus.NOK
                self.io_handler.show_result(
                    step.id,
                    execution.stdout or "",
                    execution.stderr or "",
                )
            else:
                result = self._execute_function(step)
                execution.result_text = self.redactor.redact(result)
                execution.stdout = self.redactor.redact(result)
                execution.status = NodeStatus.OK
                self.io_handler.show_result(step.id, execution.stdout or "", "")
        except Exception as error:
            execution.status = NodeStatus.NOK
            execution.exception = self.redactor.redact(error)
            execution.stderr = self.redactor.redact(error)
            self.io_handler.show_result(step.id, "", execution.stderr or "")
        execution.end_time = self.clock.now()
        execution.duration_ms = int(
            (execution.end_time - execution.start_time).total_seconds() * 1000
        )
        self.node_repo.create_execution(execution)
        return execution

    def _execute_function(self, step: FunctionStep) -> Any:
        plugin = self.plugins.get_plugin(step.plugin, step.config)
        try:
            plugin.validate_function_params(step.function, step.params)
            return plugin.execute(step.function, step.params)
        finally:
            plugin.cleanup()

    def _redacted_step(self, step: Step) -> Step:
        updates: dict[str, Any] = {}
        for field_name in ("instructions", "command", "prompt", "verify"):
            if hasattr(step, field_name):
                value = getattr(step, field_name)
                if value is not None:
                    updates[field_name] = self.redactor.redact(value)
        return step.model_copy(update=updates)

    def _record_without_execution(
        self,
        workflow_id: str,
        run_id: int,
        step_id: str,
        status: NodeStatus,
        decision: str,
        attempt: int = 1,
    ) -> NodeExecution:
        now = self.clock.now()
        execution = NodeExecution(
            workflow_name=workflow_id,
            run_id=run_id,
            node_id=step_id,
            attempt=attempt,
            start_time=now,
            end_time=now,
            status=status,
            operator_decision=decision,
            duration_ms=0,
        )
        self.node_repo.create_execution(execution)
        return execution

    @staticmethod
    def _count(execution: NodeExecution, run_info: RunInfo) -> None:
        if execution.status == NodeStatus.OK:
            run_info.nodes_ok += 1
        elif execution.status == NodeStatus.NOK:
            run_info.nodes_nok += 1
        elif execution.status in (NodeStatus.SKIPPED, NodeStatus.DISABLED):
            run_info.nodes_skipped += 1
