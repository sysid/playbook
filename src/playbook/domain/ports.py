from datetime import datetime
from typing import Protocol

from .models import NodeExecution, RunInfo, Runbook, Step


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current UTC time."""


class ProcessRunner(Protocol):
    def run_command(
        self,
        command: str,
        timeout: int,
        interactive: bool = False,
    ) -> tuple[int, str, str]:
        """Run a command and return exit code, stdout, and stderr."""


class RunRepository(Protocol):
    def create_run(self, run_info: RunInfo) -> int:
        """Create a run and return its sequence number."""

    def update_run(self, run_info: RunInfo) -> None:
        """Persist the current run state."""

    def get_run(self, workflow_name: str, run_id: int) -> RunInfo:
        """Return one run."""

    def list_runs(self, workflow_name: str) -> list[RunInfo]:
        """Return all runs for a workflow."""


class NodeExecutionRepository(Protocol):
    def create_execution(self, execution: NodeExecution) -> None:
        """Record a step execution."""

    def update_execution(self, execution: NodeExecution) -> None:
        """Update a step execution."""

    def get_executions(
        self,
        workflow_name: str,
        run_id: int,
    ) -> list[NodeExecution]:
        """Return all step executions for a run."""

    def get_latest_execution_attempt(
        self,
        workflow_name: str,
        run_id: int,
        node_id: str,
    ) -> NodeExecution | None:
        """Return the latest execution attempt for a step."""


class NodeIOHandler(Protocol):
    def show_step(
        self,
        runbook: Runbook,
        step: Step,
        position: int,
        total: int,
    ) -> None:
        """Display one step with workflow position."""

    def choose(self, prompt: str, choices: tuple[str, ...]) -> str:
        """Ask the operator to choose one allowed action."""

    def show_result(self, step_id: str, stdout: str, stderr: str) -> None:
        """Display redacted step output."""
