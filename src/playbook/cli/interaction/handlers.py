import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ...domain.models import CommandStep, FunctionStep, Runbook, Step
from ...domain.ports import Clock, NodeIOHandler


class SystemClock(Clock):
    def now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)


class ConsoleNodeIOHandler(NodeIOHandler):
    def __init__(self, console: Console):
        self.console = console

    def show_step(
        self,
        runbook: Runbook,
        step: Step,
        position: int,
        total: int,
    ) -> None:
        title = f"{runbook.title} / step {position} of {total} / {step.name or step.id}"
        lines = [step.instructions or "No instructions provided."]
        if isinstance(step, CommandStep):
            lines.extend(("", f"$ {step.command}"))
        elif isinstance(step, FunctionStep):
            lines.extend(("", f"{step.plugin}:{step.function}"))
        self.console.print(Panel("\n".join(lines), title=title, expand=False))

    def choose(self, prompt: str, choices: tuple[str, ...]) -> str:
        return Prompt.ask(prompt, choices=list(choices), default=choices[0])

    def show_result(self, step_id: str, stdout: str, stderr: str) -> None:
        if stdout.strip():
            self.console.print(f"[bold]Output from {step_id}[/bold]")
            self.console.print(stdout.rstrip())
        if stderr.strip():
            self.console.print(f"[bold red]Error from {step_id}[/bold red]")
            self.console.print(stderr.rstrip())
