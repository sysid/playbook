# tests/test_service/test_statistics.py
"""Tests for the statistics service."""

from unittest.mock import Mock

import pytest

from playbook.service.statistics import StatisticsService


class TestStatisticsService:
    """Test cases for the StatisticsService."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock statistics repository."""
        return Mock()

    @pytest.fixture
    def service(self, mock_repository):
        """Create a statistics service instance."""
        return StatisticsService(mock_repository)

    def test_get_database_info(self, service, mock_repository):
        """Test getting database info."""
        expected_info = {
            "path": "/test/path/db.sqlite",
            "size_kb": 1024.5,
            "exists": True,
        }
        mock_repository.get_database_info.return_value = expected_info

        result = service.get_database_info()

        assert result == expected_info
        mock_repository.get_database_info.assert_called_once()

    def test_get_workflow_statistics(self, service, mock_repository):
        """Test getting workflow statistics."""
        expected_stats = {
            "workflow1": {
                "total_runs": 10,
                "status_counts": {"ok": 8, "nok": 2},
                "latest_run": "2025-01-20T12:00:00Z",
            },
            "workflow2": {
                "total_runs": 5,
                "status_counts": {"ok": 3, "nok": 1, "running": 1},
                "latest_run": "2025-01-20T13:00:00Z",
            },
        }
        mock_repository.get_workflow_stats.return_value = expected_stats

        result = service.get_workflow_statistics()

        assert result == expected_stats
        mock_repository.get_workflow_stats.assert_called_once()

    def test_get_node_statistics(self, service, mock_repository):
        """Test getting node statistics."""
        expected_stats = {
            "workflow1.node1": {
                "workflow_name": "workflow1",
                "node_id": "node1",
                "status_counts": {"ok": 8, "nok": 2},
            },
            "workflow1.node2": {
                "workflow_name": "workflow1",
                "node_id": "node2",
                "status_counts": {"ok": 10},
            },
        }
        mock_repository.get_node_stats.return_value = expected_stats

        result = service.get_node_statistics()

        assert result == expected_stats
        mock_repository.get_node_stats.assert_called_once()

    def test_get_schema_information(self, service, mock_repository):
        """Test getting database schema."""
        expected_schema = {
            "runs": [
                {"name": "workflow_name", "type": "TEXT"},
                {"name": "run_id", "type": "INTEGER"},
                {"name": "status", "type": "TEXT"},
            ],
            "node_executions": [
                {"name": "workflow_name", "type": "TEXT"},
                {"name": "node_id", "type": "TEXT"},
                {"name": "status", "type": "TEXT"},
            ],
        }
        mock_repository.get_database_schema.return_value = expected_schema

        result = service.get_schema_information()

        assert result == expected_schema
        mock_repository.get_database_schema.assert_called_once()

    def test_get_schema_ddl(self, service, mock_repository):
        """Test getting schema DDL."""
        expected_ddl = [
            "CREATE TABLE runs (workflow_name TEXT, run_id INTEGER, status TEXT)",
            "CREATE TABLE node_executions (workflow_name TEXT, node_id TEXT, status TEXT)",
        ]
        mock_repository.get_schema_ddl.return_value = expected_ddl

        result = service.get_schema_ddl()

        assert result == expected_ddl
        mock_repository.get_schema_ddl.assert_called_once()

    def test_service_delegates_to_repository(self, service, mock_repository):
        """Test that service properly delegates all calls to repository."""
        # Call all methods
        service.get_database_info()
        service.get_workflow_statistics()
        service.get_node_statistics()
        service.get_schema_information()
        service.get_schema_ddl()

        # Verify all repository methods were called
        mock_repository.get_database_info.assert_called_once()
        mock_repository.get_workflow_stats.assert_called_once()
        mock_repository.get_node_stats.assert_called_once()
        mock_repository.get_database_schema.assert_called_once()
        mock_repository.get_schema_ddl.assert_called_once()
