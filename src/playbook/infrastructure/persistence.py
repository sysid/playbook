from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..domain.models import (
    NodeExecution,
    NodeStatus,
    RunInfo,
    RunStatus,
    TriggerType,
    WorkflowSummary,
)
from ..domain.ports import NodeExecutionRepository, RunRepository


class SQLiteRepository:
    SCHEMA_VERSION = 1
    TABLES = {"runs", "executions"}

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                    """
                )
            }
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if tables:
                if version != self.SCHEMA_VERSION or tables != self.TABLES:
                    raise RuntimeError(
                        "Incompatible state database; archive or delete it and "
                        "start with a fresh state database"
                    )
                return
            if version != 0:
                raise RuntimeError(
                    "Invalid state database; archive or delete it and start with "
                    "a fresh state database"
                )

            connection.executescript(
                """
                CREATE TABLE runs (
                    workflow_name TEXT NOT NULL,
                    run_id INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT NOT NULL,
                    nodes_ok INTEGER NOT NULL DEFAULT 0,
                    nodes_nok INTEGER NOT NULL DEFAULT 0,
                    nodes_skipped INTEGER NOT NULL DEFAULT 0,
                    trigger TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    definition_hash TEXT NOT NULL,
                    variables_json TEXT NOT NULL,
                    PRIMARY KEY (workflow_name, run_id)
                );

                CREATE TABLE executions (
                    workflow_name TEXT NOT NULL,
                    run_id INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT NOT NULL,
                    operator_decision TEXT,
                    result_text TEXT,
                    exit_code INTEGER,
                    exception TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    duration_ms INTEGER,
                    PRIMARY KEY (workflow_name, run_id, node_id, attempt),
                    FOREIGN KEY (workflow_name, run_id)
                        REFERENCES runs (workflow_name, run_id)
                );
                """
            )
            connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")

    @staticmethod
    def _datetime_to_str(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _str_to_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    @classmethod
    def _required_datetime(cls, value: str | None) -> datetime:
        parsed = cls._str_to_datetime(value)
        if parsed is None:
            raise ValueError("Persisted start_time cannot be empty")
        return parsed


class SQLiteRunRepository(SQLiteRepository, RunRepository):
    def create_run(self, run_info: RunInfo) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COALESCE(MAX(run_id), 0) + 1 AS next_id
                FROM runs
                WHERE workflow_name = ?
                """,
                (run_info.workflow_name,),
            ).fetchone()
            run_id = int(row["next_id"])
            connection.execute(
                """
                INSERT INTO runs (
                    workflow_name, run_id, start_time, end_time, status,
                    nodes_ok, nodes_nok, nodes_skipped, trigger, source_path,
                    definition_hash, variables_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_info.workflow_name,
                    run_id,
                    self._datetime_to_str(run_info.start_time),
                    self._datetime_to_str(run_info.end_time),
                    run_info.status.value,
                    run_info.nodes_ok,
                    run_info.nodes_nok,
                    run_info.nodes_skipped,
                    run_info.trigger.value,
                    run_info.source_path,
                    run_info.definition_hash,
                    json.dumps(run_info.variables, sort_keys=True),
                ),
            )
            return run_id

    def update_run(self, run_info: RunInfo) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET end_time = ?, status = ?, nodes_ok = ?, nodes_nok = ?,
                    nodes_skipped = ?, source_path = ?, definition_hash = ?,
                    variables_json = ?
                WHERE workflow_name = ? AND run_id = ?
                """,
                (
                    self._datetime_to_str(run_info.end_time),
                    run_info.status.value,
                    run_info.nodes_ok,
                    run_info.nodes_nok,
                    run_info.nodes_skipped,
                    run_info.source_path,
                    run_info.definition_hash,
                    json.dumps(run_info.variables, sort_keys=True),
                    run_info.workflow_name,
                    run_info.run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    f"Run not found: {run_info.workflow_name}/{run_info.run_id}"
                )

    def get_run(self, workflow_name: str, run_id: int) -> RunInfo:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE workflow_name = ? AND run_id = ?",
                (workflow_name, run_id),
            ).fetchone()
        if row is None:
            raise ValueError(f"Run not found: {workflow_name}/{run_id}")
        return self._run_from_row(row)

    def list_runs(self, workflow_name: str) -> list[RunInfo]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM runs
                WHERE workflow_name = ?
                ORDER BY run_id DESC
                """,
                (workflow_name,),
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def list_workflows(self) -> list[WorkflowSummary]:
        # The join picks the latest run per workflow explicitly rather than
        # relying on SQLite's bare-column-with-MAX behaviour.
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    runs.workflow_name,
                    latest.run_count,
                    runs.start_time,
                    runs.status
                FROM runs
                JOIN (
                    SELECT
                        workflow_name,
                        COUNT(*) AS run_count,
                        MAX(run_id) AS last_run_id
                    FROM runs
                    GROUP BY workflow_name
                ) AS latest
                  ON latest.workflow_name = runs.workflow_name
                 AND latest.last_run_id = runs.run_id
                ORDER BY runs.start_time DESC, runs.workflow_name ASC
                """
            ).fetchall()
        return [
            WorkflowSummary(
                workflow_name=row["workflow_name"],
                run_count=row["run_count"],
                last_start_time=self._required_datetime(row["start_time"]),
                last_status=RunStatus(row["status"]),
            )
            for row in rows
        ]

    def _run_from_row(self, row: sqlite3.Row) -> RunInfo:
        return RunInfo(
            workflow_name=row["workflow_name"],
            run_id=row["run_id"],
            start_time=self._required_datetime(row["start_time"]),
            end_time=self._str_to_datetime(row["end_time"]),
            status=RunStatus(row["status"]),
            nodes_ok=row["nodes_ok"],
            nodes_nok=row["nodes_nok"],
            nodes_skipped=row["nodes_skipped"],
            trigger=TriggerType(row["trigger"]),
            source_path=row["source_path"],
            definition_hash=row["definition_hash"],
            variables=json.loads(row["variables_json"]),
        )


class SQLiteNodeExecutionRepository(SQLiteRepository, NodeExecutionRepository):
    def create_execution(self, execution: NodeExecution) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO executions (
                    workflow_name, run_id, node_id, attempt, start_time,
                    end_time, status, operator_decision, result_text, exit_code,
                    exception, stdout, stderr, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._execution_values(execution),
            )

    def update_execution(self, execution: NodeExecution) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE executions
                SET end_time = ?, status = ?, operator_decision = ?,
                    result_text = ?, exit_code = ?, exception = ?, stdout = ?,
                    stderr = ?, duration_ms = ?
                WHERE workflow_name = ? AND run_id = ?
                    AND node_id = ? AND attempt = ?
                """,
                (
                    self._datetime_to_str(execution.end_time),
                    execution.status.value,
                    execution.operator_decision,
                    execution.result_text,
                    execution.exit_code,
                    execution.exception,
                    execution.stdout,
                    execution.stderr,
                    execution.duration_ms,
                    execution.workflow_name,
                    execution.run_id,
                    execution.node_id,
                    execution.attempt,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    "Execution not found: "
                    f"{execution.workflow_name}/{execution.run_id}/"
                    f"{execution.node_id}/{execution.attempt}"
                )

    def get_executions(self, workflow_name: str, run_id: int) -> list[NodeExecution]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM executions
                WHERE workflow_name = ? AND run_id = ?
                ORDER BY start_time, node_id, attempt
                """,
                (workflow_name, run_id),
            ).fetchall()
        return [self._execution_from_row(row) for row in rows]

    def get_latest_execution_attempt(
        self, workflow_name: str, run_id: int, node_id: str
    ) -> NodeExecution | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM executions
                WHERE workflow_name = ? AND run_id = ? AND node_id = ?
                ORDER BY attempt DESC
                LIMIT 1
                """,
                (workflow_name, run_id, node_id),
            ).fetchone()
        return self._execution_from_row(row) if row else None

    def _execution_values(self, execution: NodeExecution) -> tuple[object, ...]:
        return (
            execution.workflow_name,
            execution.run_id,
            execution.node_id,
            execution.attempt,
            self._datetime_to_str(execution.start_time),
            self._datetime_to_str(execution.end_time),
            execution.status.value,
            execution.operator_decision,
            execution.result_text,
            execution.exit_code,
            execution.exception,
            execution.stdout,
            execution.stderr,
            execution.duration_ms,
        )

    def _execution_from_row(self, row: sqlite3.Row) -> NodeExecution:
        return NodeExecution(
            workflow_name=row["workflow_name"],
            run_id=row["run_id"],
            node_id=row["node_id"],
            attempt=row["attempt"],
            start_time=self._required_datetime(row["start_time"]),
            end_time=self._str_to_datetime(row["end_time"]),
            status=NodeStatus(row["status"]),
            operator_decision=row["operator_decision"],
            result_text=row["result_text"],
            exit_code=row["exit_code"],
            exception=row["exception"],
            stdout=row["stdout"],
            stderr=row["stderr"],
            duration_ms=row["duration_ms"],
        )
