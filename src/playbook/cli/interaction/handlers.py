import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from ...domain.models import CommandStep, FunctionStep, Runbook, Step
from ...domain.ports import Clock, NodeIOHandler

# Panels keep one width for the whole run so steps do not jump around as
# instructions and commands change length. Narrow terminals win over it.
MAX_PANEL_WIDTH = 100


class SystemClock(Clock):
    def now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)


class ConsoleNodeIOHandler(NodeIOHandler):
    def __init__(self, console: Console):
        self.console = console

    @property
    def panel_width(self) -> int:
        return min(self.console.width, MAX_PANEL_WIDTH)

    def show_step(
        self,
        runbook: Runbook,
        step: Step,
        position: int,
        total: int,
    ) -> None:
        title = f"{runbook.title} / step {position} of {total} / {step.name or step.id}"
        body = Text(step.instructions or "No instructions provided.")
        if isinstance(step, CommandStep):
            body.append("\n\n")
            body.append(f"$ {step.command}", style="cyan")
        elif isinstance(step, FunctionStep):
            body.append("\n\n")
            body.append(f"{step.plugin}:{step.function}", style="cyan")

        self.console.print()
        self.console.print(
            Panel(
                body,
                title=title,
                title_align="left",
                width=self.panel_width,
                padding=(1, 2),
            )
        )

    def choose(self, prompt: str, choices: tuple[str, ...]) -> str:
        self.console.print()
        return Prompt.ask(f"  {prompt}", choices=list(choices), default=choices[0])

    def show_result(self, step_id: str, stdout: str, stderr: str) -> None:
        if stdout.strip():
            self.console.print()
            self.console.print(f"  [bold]Output from {step_id}[/bold]")
            self.console.print(Text(self._indent(stdout), style="dim"))
        if stderr.strip():
            self.console.print()
            self.console.print(f"  [bold red]Error from {step_id}[/bold red]")
            self.console.print(Text(self._indent(stderr), style="red"))

    @staticmethod
    def _indent(text: str) -> str:
        """Align output with panel content without padding to the console width."""
        return "\n".join(f"  {line}" for line in text.rstrip().splitlines())
