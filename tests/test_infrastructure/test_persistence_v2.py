import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

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


def run_info() -> RunInfo:
    return RunInfo(
        workflow_name="daily",
        run_id=0,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=RunStatus.RUNNING,
        trigger=TriggerType.RUN,
        source_path="/runbooks/daily.playbook.toml",
        definition_hash="abc123",
        variables={"ENVIRONMENT": "test"},
    )


def test_createRun_whenVersionTwoMetadataProvided_thenRoundTrips(
    tmp_path: Path,
) -> None:
    repository = SQLiteRunRepository(str(tmp_path / "runs.db"))
    expected = run_info()

    expected.run_id = repository.create_run(expected)
    actual = repository.get_run("daily", expected.run_id)

    assert actual.source_path == expected.source_path
    assert actual.definition_hash == "abc123"
    assert actual.variables == {"ENVIRONMENT": "test"}


def test_initialize_whenDatabaseIsNew_thenMarksCurrentSchema(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runs.db"

    SQLiteRunRepository(str(database))

    with sqlite3.connect(database) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1


def test_createExecution_whenRunDoesNotExist_thenForeignKeyRejectsIt(
    tmp_path: Path,
) -> None:
    repository = SQLiteNodeExecutionRepository(str(tmp_path / "runs.db"))
    execution = NodeExecution(
        workflow_name="missing",
        run_id=1,
        node_id="step",
        attempt=1,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=NodeStatus.OK,
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_execution(execution)


def test_createRun_whenCalledTwice_thenAllocatesSequentialIds(
    tmp_path: Path,
) -> None:
    repository = SQLiteRunRepository(str(tmp_path / "runs.db"))

    first = repository.create_run(run_info())
    second = repository.create_run(run_info())

    assert (first, second) == (1, 2)


def test_initialize_whenUnversionedDatabaseExists_thenRejectsIt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE runs (workflow_name TEXT)")

    with pytest.raises(RuntimeError, match="fresh state database"):
        SQLiteRunRepository(str(database))
