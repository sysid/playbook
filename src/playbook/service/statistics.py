# src/playbook/service/statistics.py
from typing import Dict, List

from ..domain.ports import StatisticsRepository


class StatisticsService:
    """Service for retrieving system statistics"""

    def __init__(self, stats_repo: StatisticsRepository):
        self.stats_repo = stats_repo

    def get_database_info(self) -> Dict:
        """Get basic database information"""
        return self.stats_repo.get_database_info()

    def get_workflow_statistics(self) -> Dict:
        """Get statistics about workflows and their runs"""
        return self.stats_repo.get_workflow_stats()

    def get_node_statistics(self) -> Dict:
        """Get statistics about node executions"""
        return self.stats_repo.get_node_stats()

    def get_schema_information(self) -> Dict:
        """Get database schema information"""
        return self.stats_repo.get_database_schema()

    def get_schema_ddl(self) -> List[str]:
        """Get database schema as DDL statements"""
        return self.stats_repo.get_schema_ddl()
