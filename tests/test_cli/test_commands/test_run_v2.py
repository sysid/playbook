from unittest.mock import Mock, patch

from playbook.cli.main import app
from playbook.domain.models import RunInfo, RunStatus, TriggerType


@patch("playbook.cli.commands.run.WorkflowLock")
@patch("playbook.cli.commands.run.get_engine")
def test_run_executes_guided_engine(
    get_engine,
    workflow_lock,
    cli_runner,
    temp_toml_file,
):
    engine = Mock()
    engine.run.return_value = RunInfo(
        workflow_name="test-workflow",
        run_id=7,
        start_time="2026-01-01T00:00:00Z",
        status=RunStatus.OK,
        trigger=TriggerType.RUN,
        source_path=temp_toml_file,
        definition_hash="abc",
    )
    get_engine.return_value = engine

    result = cli_runner.invoke(
        app,
        ["run", temp_toml_file, "--state-path", "/tmp/playbook-test.db"],
    )

    assert result.exit_code == 0
    engine.run.assert_called_once()
    assert engine.run.call_args.args[0].id == "test-workflow"
    workflow_lock.assert_called_once()
    assert "Run 7 finished with status: ok" in result.output


@patch("playbook.cli.commands.run.WorkflowLock")
@patch("playbook.cli.commands.run.get_engine")
def test_resume_uses_latest_aborted_run(
    get_engine,
    workflow_lock,
    cli_runner,
    temp_toml_file,
):
    engine = Mock()
    engine.run_repo.list_runs.return_value = [
        RunInfo(
            workflow_name="test-workflow",
            run_id=2,
            start_time="2026-01-01T00:00:00Z",
            status=RunStatus.OK,
            trigger=TriggerType.RUN,
            source_path=temp_toml_file,
            definition_hash="abc",
        ),
        RunInfo(
            workflow_name="test-workflow",
            run_id=3,
            start_time="2026-01-01T00:00:00Z",
            status=RunStatus.ABORTED,
            trigger=TriggerType.RUN,
            source_path=temp_toml_file,
            definition_hash="abc",
        ),
    ]
    engine.resume.return_value = engine.run_repo.list_runs.return_value[1]
    get_engine.return_value = engine

    result = cli_runner.invoke(
        app,
        ["resume", temp_toml_file, "--state-path", "/tmp/playbook-test.db"],
    )

    assert result.exit_code == 0
    engine.resume.assert_called_once()
    assert engine.resume.call_args.args[1] == 3
