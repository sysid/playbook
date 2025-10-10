# src/playbook/infrastructure/statistics.py
import sqlite3
from pathlib import Path
from typing import Dict, List, Any

from ..domain.ports import StatisticsRepository


class SQLiteStatisticsRepository(StatisticsRepository):
    """SQLite implementation of statistics repository"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser()

    def get_database_info(self) -> Dict[str, Any]:
        """Get basic database information"""
        if not self.db_path.exists():
            return {"exists": False, "path": str(self.db_path)}

        return {
            "exists": True,
            "path": str(self.db_path),
            "size_kb": self.db_path.stat().st_size / 1024,
        }

    def get_workflow_stats(self) -> Dict[str, Dict]:
        """Get statistics for all workflows"""
        if not self.db_path.exists():
            return {}

        result = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get workflow statistics
            cursor = conn.execute(
                "SELECT workflow_name, COUNT(*) as run_count FROM runs GROUP BY workflow_name"
            )
            workflows = cursor.fetchall()

            for workflow in workflows:
                workflow_name = workflow["workflow_name"]

                # Get status counts
                status_cursor = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM runs
                    WHERE workflow_name = ?
                    GROUP BY status
                    """,
                    (workflow_name,),
                )
                status_counts = {row["status"]: row["count"] for row in status_cursor}

                # Get latest run
                latest_cursor = conn.execute(
                    """
                    SELECT run_id, start_time, status
                    FROM runs
                    WHERE workflow_name = ?
                    ORDER BY run_id DESC LIMIT 1
                    """,
                    (workflow_name,),
                )
                latest = latest_cursor.fetchone()

                result[workflow_name] = {
                    "total_runs": workflow["run_count"],
                    "status_counts": status_counts,
                    "latest_run_id": latest["run_id"] if latest else None,
                    "latest_run": latest["start_time"] if latest else None,
                    "latest_status": latest["status"] if latest else None,
                }

        return result

    def get_node_stats(self) -> Dict[str, Dict]:
        """Get statistics for all nodes"""
        if not self.db_path.exists():
            return {}

        result = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get node statistics
            node_cursor = conn.execute(
                """
                SELECT workflow_name, node_id, status, COUNT(*) as count
                FROM executions
                GROUP BY workflow_name, node_id, status
                """
            )
            node_stats = node_cursor.fetchall()

            for stat in node_stats:
                key = f"{stat['workflow_name']}:{stat['node_id']}"
                if key not in result:
                    result[key] = {
                        "workflow_name": stat["workflow_name"],
                        "node_id": stat["node_id"],
                        "status_counts": {
                            "ok": 0,
                            "nok": 0,
                            "skipped": 0,
                            "pending": 0,
                            "running": 0,
                        },
                    }

                result[key]["status_counts"][stat["status"]] = stat["count"]

        return result

    def get_database_schema(self) -> Dict[str, List[Dict]]:
        """Get database schema information"""
        if not self.db_path.exists():
            return {}

        schema = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get table names
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table["name"]

                # Skip SQLite internal tables
                if table_name.startswith("sqlite_"):
                    continue

                schema[table_name] = {"columns": [], "indexes": []}

                # Get table schema
                schema_cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = schema_cursor.fetchall()

                for col in columns:
                    schema[table_name]["columns"].append(
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "not_null": bool(col["notnull"]),
                            "default": col["dflt_value"],
                            "primary_key": bool(col["pk"]),
                        }
                    )

                # Get indexes
                index_cursor = conn.execute(f"PRAGMA index_list({table_name})")
                indexes = index_cursor.fetchall()

                for idx in indexes:
                    index_info = {
                        "name": idx["name"],
                        "unique": bool(idx["unique"]),
                        "columns": [],
                    }

                    # Get indexed columns
                    idx_info_cursor = conn.execute(f"PRAGMA index_info({idx['name']})")
                    for col in idx_info_cursor:
                        index_info["columns"].append(col["name"])

                    schema[table_name]["indexes"].append(index_info)

        return schema

    def get_schema_ddl(self) -> List[str]:
        """Get database schema as DDL statements"""
        if not self.db_path.exists():
            return []

        ddl_statements = []

        with sqlite3.connect(self.db_path) as conn:
            # Get table DDL
            cursor = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()

            for table in tables:
                if table[1]:  # sql might be None for some internal tables
                    ddl_statements.append(table[1])

            # Get index DDL
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            indexes = cursor.fetchall()

            for index in indexes:
                if index[0]:  # sql might be None for some internal indexes
                    ddl_statements.append(index[0])

        return ddl_statements
