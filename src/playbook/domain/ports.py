# src/playbook/domain/ports.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Protocol, Any, Optional

from .models import NodeExecution, RunInfo, Runbook


class Clock(Protocol):
    """Time provider interface"""

    @abstractmethod
    def now(self) -> datetime:
        """Get current time"""
        pass


class ProcessRunner(Protocol):
    """Command execution interface"""

    @abstractmethod
    def run_command(
        self, command: str, timeout: int, interactive: bool = False
    ) -> tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr

        Args:
            command: The command to run
            timeout: Timeout in seconds
            interactive: Whether the command needs interactive input
        """
        pass


class FunctionLoader(Protocol):
    """Dynamic function loading interface"""

    @abstractmethod
    def load_and_call(self, function_path: str, params: Dict) -> any:
        """Load function by its path and call with params"""
        pass


class RunRepository(ABC):
    """Interface for run persistence"""

    @abstractmethod
    def create_run(self, run_info: RunInfo) -> int:
        """Create a new run and return run ID"""
        pass

    @abstractmethod
    def update_run(self, run_info: RunInfo) -> None:
        """Update run status"""
        pass

    @abstractmethod
    def get_run(self, workflow_name: str, run_id: int) -> RunInfo:
        """Get run by ID"""
        pass

    @abstractmethod
    def list_runs(self, workflow_name: str) -> List[RunInfo]:
        """List all runs for a workflow"""
        pass


class NodeExecutionRepository(ABC):
    """Interface for node execution persistence"""

    @abstractmethod
    def create_execution(self, execution: NodeExecution) -> None:
        """Record a node execution"""
        pass

    @abstractmethod
    def update_execution(self, execution: NodeExecution) -> None:
        """Update node execution status"""
        pass

    @abstractmethod
    def get_executions(self, workflow_name: str, run_id: int) -> List[NodeExecution]:
        """Get all executions for a run"""
        pass

    @abstractmethod
    def get_latest_execution_attempt(
        self, workflow_name: str, run_id: int, node_id: str
    ) -> Optional[NodeExecution]:
        """Get the latest execution attempt for a specific node"""
        pass


class StatisticsRepository(Protocol):
    """Interface for retrieving system statistics"""

    @abstractmethod
    def get_database_info(self) -> Dict[str, Any]:
        """Get basic database information"""
        pass

    @abstractmethod
    def get_workflow_stats(self) -> Dict[str, Dict]:
        """Get statistics about workflows and their runs"""
        pass

    @abstractmethod
    def get_node_stats(self) -> Dict[str, Dict]:
        """Get statistics about node executions"""
        pass

    @abstractmethod
    def get_database_schema(self) -> Dict[str, List[Dict]]:
        """Get database schema information"""
        pass

    @abstractmethod
    def get_schema_ddl(self) -> List[str]:
        """Get database schema as DDL statements"""
        pass


class Visualizer(Protocol):
    """Graphviz visualization interface"""

    @abstractmethod
    def export_dot(self, runbook: Runbook, output_path: str) -> None:
        """Export runbook as DOT file"""
        pass


class CommandOutputHandler(Protocol):
    """Interface for handling command output"""

    @abstractmethod
    def handle_output(
        self, node_id: str, node_name: Optional[str], stdout: str, stderr: str
    ) -> None:
        """Handle command output"""
        pass


class NodeIOHandler(Protocol):
    """Interface for handling node input/output"""

    def handle_prompt(
        self,
        node_id: str,
        node_name: Optional[str],
        prompt: str,
    ) -> bool:
        """Handle manual node prompt, returns user decision (True/False)"""
        pass

    def handle_description_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
    ) -> None:
        """Handle manual node prompt, returns user decision (True/False)"""
        pass

    def handle_command_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        stdout: str,
        stderr: str,
    ) -> None:
        """Handle command output"""
        pass

    def handle_function_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        result: str,
    ) -> None:
        """Handle function output"""
        pass
