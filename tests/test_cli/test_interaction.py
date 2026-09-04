from rich.console import Console

from playbook.cli.interaction.handlers import ConsoleNodeIOHandler
from playbook.domain.models import ManualStep, Runbook


def test_step_header_orients_operator():
    console = Console(record=True, width=100)
    handler = ConsoleNodeIOHandler(console)
    runbook = Runbook(
        id="daily",
        title="Daily checks",
        steps=[],
        source_path="/runbooks/daily.playbook.toml",
        definition_hash="abc",
    )
    step = ManualStep(
        id="review",
        type="manual",
        name="Review alerts",
        instructions="Open the alerts dashboard.",
    )

    handler.show_step(runbook, step, 2, 4)

    output = console.export_text()
    assert "Daily checks / step 2 of 4 / Review alerts" in output
    assert "Open the alerts dashboard." in output
