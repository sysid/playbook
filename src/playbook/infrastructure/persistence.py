# src/playbook/infrastructure/persistence.py
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..domain.models import NodeExecution, NodeStatus, RunInfo, RunStatus, TriggerType
from ..domain.ports import RunRepository, NodeExecutionRepository


class SQLiteRepository:
    """SQLite implementation of repositories"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database if it doesn't exist
        self._init_db()

    def _init_db(self):
        """Create schema if needed"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                               CREATE TABLE IF NOT EXISTS runs
                               (
                                   workflow_name
                                   TEXT,
                                   run_id
                                   INTEGER,
                                   start_time
                                   TEXT,
                                   end_time
                                   TEXT,
                                   status
                                   TEXT,
                                   nodes_ok
                                   INTEGER
                                   DEFAULT
                                   0,
                                   nodes_nok
                                   INTEGER
                                   DEFAULT
                                   0,
                                   nodes_skipped
                                   INTEGER
                                   DEFAULT
                                   0,
                                   trigger
                                   TEXT,
                                   PRIMARY
                                   KEY
                               (
                                   workflow_name,
                                   run_id
                               )
                                   );

                               CREATE TABLE IF NOT EXISTS executions
                               (
                                   workflow_name
                                   TEXT,
                                   run_id
                                   INTEGER,
                                   node_id
                                   TEXT,
                                   attempt
                                   INTEGER,
                                   start_time
                                   TEXT,
                                   end_time
                                   TEXT,
                                   status
                                   TEXT,
                                   operator_decision
                                   TEXT,
                                   result_text
                                   TEXT,
                                   exit_code
                                   INTEGER,
                                   exception
                                   TEXT,
                                   stdout
                                   TEXT,
                                   stderr
                                   TEXT,
                                   duration_ms
                                   INTEGER,
                                   PRIMARY
                                   KEY
                               (
                                   workflow_name,
                                   run_id,
                                   node_id,
                                   attempt
                               ),
                                   FOREIGN KEY
                               (
                                   workflow_name,
                                   run_id
                               ) REFERENCES runs
                               (
                                   workflow_name,
                                   run_id
                               )
                                   );
                               """)

    def _datetime_to_str(self, dt: Optional[datetime]) -> Optional[str]:
        """Convert datetime to ISO string"""
        return dt.isoformat() if dt else None

    def _str_to_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Convert ISO string to datetime"""
        return datetime.fromisoformat(dt_str) if dt_str else None


class SQLiteRunRepository(SQLiteRepository, RunRepository):
    """SQLite implementation of RunRepository"""

    def create_run(self, run_info: RunInfo) -> int:
        """Create a new run and return run ID"""
        with sqlite3.connect(self.db_path) as conn:
            # Get next run_id
            cursor = conn.execute(
                "SELECT COALESCE(MAX(run_id), 0) + 1 FROM runs WHERE workflow_name = ?",
                (run_info.workflow_name,),
            )
            run_id = cursor.fetchone()[0]

            # Insert run
            conn.execute(
                """
                INSERT INTO runs (workflow_name, run_id, start_time, end_time,
                                  status, nodes_ok, nodes_nok, nodes_skipped, trigger)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

            return run_id

    def update_run(self, run_info: RunInfo) -> None:
        """Update run status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE runs
                SET end_time      = ?,
                    status        = ?,
                    nodes_ok      = ?,
                    nodes_nok     = ?,
                    nodes_skipped = ?
                WHERE workflow_name = ?
                  AND run_id = ?
                """,
                (
                    self._datetime_to_str(run_info.end_time),
                    run_info.status.value,
                    run_info.nodes_ok,
                    run_info.nodes_nok,
                    run_info.nodes_skipped,
                    run_info.workflow_name,
                    run_info.run_id,
                ),
            )

    def get_run(self, workflow_name: str, run_id: int) -> RunInfo:
        """Get run by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM runs WHERE workflow_name = ? AND run_id = ?",
                (workflow_name, run_id),
            )
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Run not found: {workflow_name}/{run_id}")

            return RunInfo(
                workflow_name=row["workflow_name"],
                run_id=row["run_id"],
                start_time=self._str_to_datetime(row["start_time"]),
                end_time=self._str_to_datetime(row["end_time"]),
                status=RunStatus(row["status"]),
                nodes_ok=row["nodes_ok"],
                nodes_nok=row["nodes_nok"],
                nodes_skipped=row["nodes_skipped"],
                trigger=TriggerType(row["trigger"]),
            )

    def list_runs(self, workflow_name: str) -> List[RunInfo]:
        """List all runs for a workflow"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM runs WHERE workflow_name = ? ORDER BY run_id DESC",
                (workflow_name,),
            )

            runs = []
            for row in cursor:
                runs.append(
                    RunInfo(
                        workflow_name=row["workflow_name"],
                        run_id=row["run_id"],
                        start_time=self._str_to_datetime(row["start_time"]),
                        end_time=self._str_to_datetime(row["end_time"]),
                        status=RunStatus(row["status"]),
                        nodes_ok=row["nodes_ok"],
                        nodes_nok=row["nodes_nok"],
                        nodes_skipped=row["nodes_skipped"],
                        trigger=TriggerType(row["trigger"]),
                    )
                )

            return runs


class SQLiteNodeExecutionRepository(SQLiteRepository, NodeExecutionRepository):
    """SQLite implementation of NodeExecutionRepository"""

    def create_execution(self, execution: NodeExecution) -> None:
        """Record a node execution"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO executions (workflow_name, run_id, node_id, attempt,
                                        start_time, end_time, status, operator_decision,
                                        result_text, exit_code, exception, stdout, stderr, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )

    def update_execution(self, execution: NodeExecution) -> None:
        """Update node execution status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE executions
                SET end_time          = ?,
                    status            = ?,
                    operator_decision = ?,
                    result_text       = ?,
                    exit_code         = ?,
                    exception         = ?,
                    stdout            = ?,
                    stderr            = ?,
                    duration_ms       = ?
                WHERE workflow_name = ?
                  AND run_id = ?
                  AND node_id = ?
                  AND attempt = ?
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

    def get_executions(self, workflow_name: str, run_id: int) -> List[NodeExecution]:
        """Get all executions for a run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT *
                FROM executions
                WHERE workflow_name = ?
                  AND run_id = ?
                ORDER BY node_id, attempt
                """,
                (workflow_name, run_id),
            )

            executions = []
            for row in cursor:
                executions.append(
                    NodeExecution(
                        workflow_name=row["workflow_name"],
                        run_id=row["run_id"],
                        node_id=row["node_id"],
                        attempt=row["attempt"],
                        start_time=self._str_to_datetime(row["start_time"]),
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
                )

            return executions

    def get_latest_execution_attempt(
        self, workflow_name: str, run_id: int, node_id: str
    ) -> Optional[NodeExecution]:
        """Get the latest execution attempt for a specific node"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM executions
                WHERE workflow_name = ? AND run_id = ? AND node_id = ?
                ORDER BY attempt DESC
                LIMIT 1
                """,
                (workflow_name, run_id, node_id),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return NodeExecution(
                workflow_name=row["workflow_name"],
                run_id=row["run_id"],
                node_id=row["node_id"],
                attempt=row["attempt"],
                start_time=self._str_to_datetime(row["start_time"]),
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
