from datetime import datetime, timezone
from typing import Any

import pytest

from playbook.domain.models import (
    CommandStep,
    ManualStep,
    NodeExecution,
    NodeStatus,
    Runbook,
    RunInfo,
    RunStatus,
    TriggerType,
    VariableDefinition,
)
from playbook.service.engine import RunbookEngine


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeProcessRunner:
    def __init__(self, results: list[tuple[int, str, str]]) -> None:
        self.results = results
        self.commands: list[str] = []

    def run_command(
        self, command: str, timeout: int, interactive: bool = False
    ) -> tuple[int, str, str]:
        self.commands.append(command)
        return self.results.pop(0)


class MemoryRunRepository:
    def __init__(self) -> None:
        self.runs: list[RunInfo] = []

    def create_run(self, run_info: RunInfo) -> int:
        run_info.run_id = len(self.runs) + 1
        self.runs.append(run_info.model_copy(deep=True))
        return run_info.run_id

    def update_run(self, run_info: RunInfo) -> None:
        self.runs[-1] = run_info.model_copy(deep=True)

    def get_run(self, workflow_name: str, run_id: int) -> RunInfo:
        for run in self.runs:
            if run.workflow_name == workflow_name and run.run_id == run_id:
                return run.model_copy(deep=True)
        raise ValueError("Run not found")

    def list_runs(self, workflow_name: str) -> list[RunInfo]:
        return [
            run.model_copy(deep=True)
            for run in self.runs
            if run.workflow_name == workflow_name
        ]


class MemoryExecutionRepository:
    def __init__(self) -> None:
        self.executions: list[NodeExecution] = []

    def create_execution(self, execution: NodeExecution) -> None:
        self.executions.append(execution.model_copy(deep=True))

    def update_execution(self, execution: NodeExecution) -> None:
        for index, current in enumerate(self.executions):
            if (
                current.node_id == execution.node_id
                and current.attempt == execution.attempt
            ):
                self.executions[index] = execution.model_copy(deep=True)
                return

    def get_executions(self, workflow_name: str, run_id: int) -> list[NodeExecution]:
        return list(self.executions)

    def get_latest_execution_attempt(
        self, workflow_name: str, run_id: int, node_id: str
    ) -> NodeExecution | None:
        matches = [item for item in self.executions if item.node_id == node_id]
        return matches[-1] if matches else None


class FakeIO:
    def __init__(self, actions: list[str]) -> None:
        self.actions = actions
        self.presented: list[tuple[str, int, int]] = []
        self.allowed_choices: list[tuple[str, ...]] = []
        self.outputs: list[tuple[str, str, str]] = []

    def show_step(
        self,
        runbook: Runbook,
        step: ManualStep | CommandStep,
        position: int,
        total: int,
    ) -> None:
        self.presented.append((step.id, position, total))

    def choose(self, prompt: str, choices: tuple[str, ...]) -> str:
        self.allowed_choices.append(choices)
        action = self.actions.pop(0)
        if action == "interrupt":
            raise KeyboardInterrupt
        assert action in choices
        return action

    def show_result(self, step_id: str, stdout: str, stderr: str) -> None:
        self.outputs.append((step_id, stdout, stderr))


def runbook_with(*steps: Any, variables: dict[str, Any] | None = None) -> Runbook:
    variable_definitions = {
        name: VariableDefinition(type="bool", default=value)
        for name, value in (variables or {}).items()
    }
    return Runbook(
        id="daily",
        title="Daily",
        steps=list(steps),
        variable_definitions=variable_definitions,
        variables=variables or {},
        definition_hash="abc",
        source_path="/tmp/daily.playbook.toml",
    )


def engine_with(
    actions: list[str],
    process_results: list[tuple[int, str, str]] | None = None,
    max_attempts: int = 3,
) -> tuple[RunbookEngine, FakeIO, MemoryExecutionRepository, FakeProcessRunner]:
    io = FakeIO(actions)
    executions = MemoryExecutionRepository()
    process = FakeProcessRunner(process_results or [])
    engine = RunbookEngine(
        clock=FixedClock(),
        process_runner=process,
        run_repo=MemoryRunRepository(),
        node_repo=executions,
        io_handler=io,
        max_attempts=max_attempts,
    )
    return engine, io, executions, process


def test_run_whenStepsSucceed_thenGuidesInFileOrder() -> None:
    engine, io, executions, process = engine_with(
        ["done", "run"],
        [(0, "healthy", "")],
    )
    runbook = runbook_with(
        ManualStep(id="login", instructions="Log in."),
        CommandStep(id="check", command="check-health"),
    )

    result = engine.run(runbook)

    assert result.status == RunStatus.OK
    assert io.presented == [("login", 1, 2), ("check", 2, 2)]
    assert process.commands == ["check-health"]
    assert [item.status for item in executions.executions] == [
        NodeStatus.OK,
        NodeStatus.OK,
    ]


def test_run_whenStepIsRequired_thenSkipIsNeverOffered() -> None:
    engine, io, _, _ = engine_with(["done"])
    runbook = runbook_with(ManualStep(id="login", instructions="Log in."))

    engine.run(runbook)

    assert io.allowed_choices == [("done", "abort")]


def test_run_whenOptionalCommandFails_thenOperatorCanRetry() -> None:
    engine, io, executions, process = engine_with(
        ["run", "retry"],
        [(1, "", "failed"), (0, "ok", "")],
    )
    runbook = runbook_with(CommandStep(id="check", command="check", required=False))

    result = engine.run(runbook)

    assert result.status == RunStatus.OK
    assert process.commands == ["check", "check"]
    assert [item.status for item in executions.executions] == [
        NodeStatus.NOK,
        NodeStatus.OK,
    ]
    assert [item.attempt for item in executions.executions] == [1, 2]


def test_run_whenRetryLimitIsReached_thenAbortsWithoutAnotherRetry() -> None:
    engine, io, executions, process = engine_with(
        ["run", "retry", "retry"],
        [(1, "", "failed")] * 3,
        max_attempts=3,
    )
    runbook = runbook_with(CommandStep(id="check", command="check"))

    result = engine.run(runbook)

    assert result.status == RunStatus.ABORTED
    assert process.commands == ["check", "check", "check"]
    assert executions.executions[-1].operator_decision == "retry-limit"
    assert io.allowed_choices[-1] == ("retry", "abort")


def test_run_whenStepIsDisabled_thenRecordsDisabledWithoutPrompting() -> None:
    engine, io, executions, _ = engine_with([])
    runbook = runbook_with(CommandStep(id="check", command="check", enabled=False))

    result = engine.run(runbook)

    assert result.status == RunStatus.OK
    assert io.presented == []
    assert executions.executions[0].status == NodeStatus.DISABLED


def test_run_whenEnabledIfIsFalse_thenRecordsDisabled() -> None:
    engine, _, executions, _ = engine_with([])
    runbook = runbook_with(
        CommandStep(id="security", command="check", enabled_if="RUN_SECURITY"),
        variables={"RUN_SECURITY": False},
    )

    engine.run(runbook)

    assert executions.executions[0].status == NodeStatus.DISABLED


def test_run_whenOperatorAborts_thenRunIsAborted() -> None:
    engine, _, executions, _ = engine_with(["abort"])
    runbook = runbook_with(ManualStep(id="login", instructions="Log in."))

    result = engine.run(runbook)

    assert result.status == RunStatus.ABORTED
    assert executions.executions[0].status == NodeStatus.ABORTED


def test_run_whenOperatorInterrupts_thenRunIsPersistedAsAborted() -> None:
    engine, _, _, _ = engine_with(["interrupt"])
    runbook = runbook_with(ManualStep(id="login", instructions="Log in."))

    with pytest.raises(KeyboardInterrupt):
        engine.run(runbook)

    assert engine.run_repo.get_run("daily", 1).status == RunStatus.ABORTED


def test_run_whenOutputContainsSecret_thenConsoleAndPersistenceAreRedacted() -> None:
    engine, io, executions, _ = engine_with(
        ["run"],
        [(0, "value=secret-value", "")],
    )
    runbook = Runbook(
        id="secret",
        title="Secret",
        steps=[CommandStep(id="show", command="show secret-value")],
        variable_definitions={
            "API_KEY": VariableDefinition(type="string", secret=True)
        },
        variables={"API_KEY": "secret-value"},
        definition_hash="abc",
        source_path="/tmp/secret.playbook.toml",
    )

    engine.run(runbook)

    assert io.outputs == [("show", "value=[REDACTED]", "")]
    assert executions.executions[0].stdout == "value=[REDACTED]"
    assert executions.executions[0].result_text == "value=[REDACTED]"


def test_resume_whenDefinitionHashDiffers_thenFailsClosed() -> None:
    run_repository = MemoryRunRepository()
    run_repository.runs.append(
        RunInfo(
            workflow_name="daily",
            run_id=1,
            start_time=FixedClock().now(),
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path="/tmp/daily.playbook.toml",
            definition_hash="old",
        )
    )
    engine = RunbookEngine(
        clock=FixedClock(),
        process_runner=FakeProcessRunner([]),
        run_repo=run_repository,
        node_repo=MemoryExecutionRepository(),
        io_handler=FakeIO([]),
    )

    with pytest.raises(ValueError, match="definition has changed"):
        engine.resume(runbook_with(), 1)


def test_resume_whenNonSecretVariablesDiffer_thenFailsClosed() -> None:
    run_repository = MemoryRunRepository()
    run_repository.runs.append(
        RunInfo(
            workflow_name="daily",
            run_id=1,
            start_time=FixedClock().now(),
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path="/tmp/daily.playbook.toml",
            definition_hash="abc",
            variables={"ENVIRONMENT": "dev"},
        )
    )
    engine = RunbookEngine(
        clock=FixedClock(),
        process_runner=FakeProcessRunner([]),
        run_repo=run_repository,
        node_repo=MemoryExecutionRepository(),
        io_handler=FakeIO([]),
    )
    runbook = Runbook(
        id="daily",
        title="Daily",
        steps=[ManualStep(id="review", instructions="Review.")],
        variable_definitions={
            "ENVIRONMENT": VariableDefinition(default="dev"),
        },
        variables={"ENVIRONMENT": "production"},
        source_path="/tmp/daily.playbook.toml",
        definition_hash="abc",
    )

    with pytest.raises(ValueError, match="variable values have changed"):
        engine.resume(runbook, 1)

    assert run_repository.get_run("daily", 1).status == RunStatus.ABORTED


def test_resume_whenCompletedStepExists_thenContinuesWithFirstIncompleteStep() -> None:
    run_repository = MemoryRunRepository()
    run_repository.runs.append(
        RunInfo(
            workflow_name="daily",
            run_id=1,
            start_time=FixedClock().now(),
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path="/tmp/daily.playbook.toml",
            definition_hash="abc",
        )
    )
    executions = MemoryExecutionRepository()
    executions.executions.append(
        NodeExecution(
            workflow_name="daily",
            run_id=1,
            node_id="login",
            attempt=1,
            start_time=FixedClock().now(),
            end_time=FixedClock().now(),
            status=NodeStatus.OK,
        )
    )
    io = FakeIO(["run"])
    process = FakeProcessRunner([(0, "ok", "")])
    engine = RunbookEngine(
        clock=FixedClock(),
        process_runner=process,
        run_repo=run_repository,
        node_repo=executions,
        io_handler=io,
    )
    runbook = runbook_with(
        ManualStep(id="login", instructions="Log in."),
        CommandStep(id="check", command="check"),
    )

    result = engine.resume(runbook, 1)

    assert result.status == RunStatus.OK
    assert io.presented == [("check", 2, 2)]
    assert process.commands == ["check"]


def test_resume_whenStepExhaustedAttempts_thenDoesNotExecuteAgain() -> None:
    run_repository = MemoryRunRepository()
    run_repository.runs.append(
        RunInfo(
            workflow_name="daily",
            run_id=1,
            start_time=FixedClock().now(),
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path="/tmp/daily.playbook.toml",
            definition_hash="abc",
        )
    )
    executions = MemoryExecutionRepository()
    executions.executions.append(
        NodeExecution(
            workflow_name="daily",
            run_id=1,
            node_id="check",
            attempt=3,
            start_time=FixedClock().now(),
            end_time=FixedClock().now(),
            status=NodeStatus.ABORTED,
            operator_decision="retry-limit",
        )
    )
    process = FakeProcessRunner([(0, "unexpected", "")])
    engine = RunbookEngine(
        clock=FixedClock(),
        process_runner=process,
        run_repo=run_repository,
        node_repo=executions,
        io_handler=FakeIO([]),
        max_attempts=3,
    )
    runbook = runbook_with(CommandStep(id="check", command="check"))

    with pytest.raises(ValueError, match="exhausted 3 attempts"):
        engine.resume(runbook, 1)

    assert process.commands == []
    assert run_repository.get_run("daily", 1).status == RunStatus.ABORTED
