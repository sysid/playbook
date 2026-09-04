from datetime import datetime, timezone

from playbook.cli.main import app
from playbook.domain.models import (
    NodeExecution,
    NodeStatus,
    RunInfo,
    RunStatus,
    TriggerType,
)
from playbook.infrastructure.persistence import (
    SQLiteNodeExecutionRepository,
    SQLiteRunRepository,
)


def test_show_lists_runs_by_workflow_id(cli_runner, temp_dir):
    database = temp_dir / "state.db"
    runs = SQLiteRunRepository(str(database))
    runs.create_run(
        RunInfo(
            workflow_name="daily",
            run_id=0,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path="/runbooks/daily.playbook.toml",
            definition_hash="abc",
        )
    )

    result = cli_runner.invoke(
        app,
        ["show", "daily", "--state-path", str(database)],
    )

    assert result.exit_code == 0
    assert "daily" in result.output
    assert "aborted" in result.output


def test_show_displays_step_executions(cli_runner, temp_dir):
    database = temp_dir / "state.db"
    now = datetime.now(timezone.utc)
    runs = SQLiteRunRepository(str(database))
    run_id = runs.create_run(
        RunInfo(
            workflow_name="daily",
            run_id=0,
            start_time=now,
            status=RunStatus.OK,
            trigger=TriggerType.RUN,
            source_path="/runbooks/daily.playbook.toml",
            definition_hash="abc",
        )
    )
    SQLiteNodeExecutionRepository(str(database)).create_execution(
        NodeExecution(
            workflow_name="daily",
            run_id=run_id,
            node_id="review",
            attempt=1,
            start_time=now,
            end_time=now,
            status=NodeStatus.OK,
        )
    )

    result = cli_runner.invoke(
        app,
        [
            "show",
            "daily",
            "--run-id",
            str(run_id),
            "--state-path",
            str(database),
        ],
    )

    assert result.exit_code == 0
    assert "daily #1" in result.output
    assert "review" in result.output
    assert "ok" in result.output


def test_show_reports_when_no_runs_exist(cli_runner, temp_dir):
    result = cli_runner.invoke(
        app,
        ["show", "unknown", "--state-path", str(temp_dir / "state.db")],
    )

    assert result.exit_code == 0
    assert "No runs found" in result.output
