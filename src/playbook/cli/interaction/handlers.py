# src/playbook/cli/interaction/handlers.py
import datetime
from typing import Optional

from rich.console import Console
from rich.progress import Progress

from ...domain.ports import Clock, NodeIOHandler


class SystemClock(Clock):
    """System clock implementation"""

    def now(self) -> datetime.datetime:
        """Get current time"""
        return datetime.datetime.now(datetime.timezone.utc)


class ConsoleNodeIOHandler(NodeIOHandler):
    """Console implementation of NodeIOHandler"""

    def __init__(self, console: Console, progress: Optional[Progress] = None):
        self.console = console
        self.displayed_descriptions = set()  # Track which nodes have shown descriptions
        self.current_node_id = None  # Track which node is currently executing
        self.progress = progress

    def set_current_node(self, node_id: str):
        """Set the current node being processed"""
        self.current_node_id = node_id

    def display_node_header(
        self, node_id: str, node_name: Optional[str], node_type: str
    ) -> None:
        """Display consistent node header for all node types"""
        display_name = node_name or node_id
        self.console.print(f"[dim]{node_type} Step ({display_name}):[/dim]")

    def handle_prompt(
        self,
        node_id: str,
        node_name: Optional[str],
        prompt: str,
    ) -> bool:
        """Display prompt and get user decision"""
        self.console.print(prompt)

        from rich.prompt import Confirm

        decision = Confirm.ask("Approve?")

        self.console.print("")
        return decision

    def handle_description_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
    ) -> None:
        """Display consistent header for manual nodes"""
        # Print description if available and not already shown
        node_key = f"{node_id}-description"
        if description and node_key not in self.displayed_descriptions:
            self.console.print(f"\n[italic]{description}[/italic]\n")
            self.displayed_descriptions.add(node_key)
        return None

    def handle_command_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        stdout: str,
        stderr: str,
    ) -> None:
        """Display command output with consistent header"""
        # Only process if there's output to show
        if not (stdout.strip() or stderr.strip()):
            return

        # We're not displaying the header here as it's already displayed at node start
        # Just show the command output

        if stdout.strip():
            self.console.print("[bold green]Command Output:[/bold green]")
            self.console.print(stdout)

        if stderr.strip():
            self.console.print("[bold yellow]Command Error:[/bold yellow]")
            self.console.print(stderr)

        self.console.print("")

    def handle_function_output(
        self,
        node_id: str,
        node_name: Optional[str],
        description: Optional[str],
        result: str,
    ) -> None:
        """Display function output with consistent header"""
        # Only process if there's output to show
        if not result.strip():
            return

        # We're not displaying the header here as it's already displayed at node start
        # Just show the function output

        # Show output
        self.console.print("[bold blue]Function Output:[/bold blue]")
        self.console.print(result)

        self.console.print("")
