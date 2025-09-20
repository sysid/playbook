# src/playbook/cli/commands/info.py
"""Info command implementation."""

import typer
from rich.table import Table

from ..common import console, handle_error_and_exit
from ...config import config_manager
from ...infrastructure.statistics import SQLiteStatisticsRepository
from ...service.statistics import StatisticsService
from ...domain.exceptions import DatabaseError


def info(
    ctx: typer.Context,
    json_format: bool = typer.Option(False, "--json", help="Output as JSON"),
    show_ddl: bool = typer.Option(False, "--ddl", help="Show database schema as DDL"),
):
    """Show database info and workflow statistics"""
    try:
        config = config_manager.get_config()

        # Create statistics service
        try:
            stats_repo = SQLiteStatisticsRepository(config.database.path)
            stats_service = StatisticsService(stats_repo)
        except Exception as e:
            raise DatabaseError(
                f"Failed to connect to statistics database: {str(e)}",
                context={"database_path": config["state_path"]},
                suggestion="Check database file permissions and that it has been initialized",
            )

        # Get database info
        db_info = stats_service.get_database_info()

        if not db_info.get("exists", False):
            console.print(f"Database does not exist yet: {db_info.get('path')}")
            console.print("Run a workflow first to create the database")
            return

        # Show database info
        console.print("[bold]Database Information:[/bold]")
        console.print(f"Path: {db_info['path']}")
        console.print(f"Size: {db_info['size_kb']:.2f} KB")

        # Show workflow statistics
        workflow_stats = stats_service.get_workflow_statistics()

        if workflow_stats:
            console.print("\n[bold]Workflow Statistics:[/bold]")

            # Create workflow stats table
            table = Table(
                "Workflow",
                "Total Runs",
                "OK",
                "NOK",
                "Running",
                "Aborted",
                "Latest Run",
            )

            for workflow_name, stats in workflow_stats.items():
                status_counts = stats["status_counts"]
                ok_count = status_counts.get("ok", 0)
                nok_count = status_counts.get("nok", 0)
                running_count = status_counts.get("running", 0)
                aborted_count = status_counts.get("aborted", 0)

                table.add_row(
                    workflow_name,
                    str(stats["total_runs"]),
                    str(ok_count),
                    str(nok_count),
                    str(running_count),
                    str(aborted_count),
                    stats["latest_run"] or "N/A",
                )

            console.print(table)

        # Show node statistics
        node_stats = stats_service.get_node_statistics()

        if node_stats:
            console.print("\n[bold]Node Statistics:[/bold]")

            # Create node stats table
            table = Table(
                "Workflow", "Node", "OK", "NOK", "Skipped", "Pending", "Running"
            )

            for key, stats in node_stats.items():
                status_counts = stats["status_counts"]

                table.add_row(
                    stats["workflow_name"],
                    stats["node_id"],
                    str(status_counts.get("ok", 0)),
                    str(status_counts.get("nok", 0)),
                    str(status_counts.get("skipped", 0)),
                    str(status_counts.get("pending", 0)),
                    str(status_counts.get("running", 0)),
                )

            console.print(table)

        # Show DDL if requested
        if show_ddl:
            console.print("\n[bold]Database Schema DDL:[/bold]")

            ddl_statements = stats_service.get_schema_ddl()

            for ddl in ddl_statements:
                console.print(f"\n{ddl};")

    except Exception as e:
        handle_error_and_exit(
            e, "Database statistics", ctx.params.get("verbose", False)
        )
