from rich.console import Console

from playbook.cli.interaction.handlers import ConsoleNodeIOHandler
from playbook.domain.models import CommandStep, ManualStep, Runbook


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


def test_step_panels_keep_one_width_regardless_of_content_length():
    console = Console(record=True, width=120)
    handler = ConsoleNodeIOHandler(console)
    runbook = Runbook(
        id="daily",
        title="daily",
        steps=[],
        source_path="/runbooks/daily.playbook.toml",
        definition_hash="abc",
    )
    short = ManualStep(id="warmup", instructions="Warm up Copilot")
    long = CommandStep(
        id="los-jira",
        instructions="Check Backlog",
        command="open " + "https://example.invalid/board?" + "x=1&" * 40,
    )

    handler.show_step(runbook, short, 1, 2)
    handler.show_step(runbook, long, 2, 2)

    border_widths = {
        len(line.rstrip())
        for line in console.export_text().splitlines()
        if line.startswith(("╭", "╰"))
    }
    assert border_widths == {100}


def test_step_panels_are_separated_by_blank_lines():
    console = Console(record=True, width=120)
    handler = ConsoleNodeIOHandler(console)
    runbook = Runbook(
        id="daily",
        title="daily",
        steps=[],
        source_path="/runbooks/daily.playbook.toml",
        definition_hash="abc",
    )

    handler.show_step(runbook, ManualStep(id="a", instructions="A"), 1, 2)
    handler.show_step(runbook, ManualStep(id="b", instructions="B"), 2, 2)

    lines = console.export_text().splitlines()
    assert lines[0].strip() == ""
    assert lines[lines.index(next(x for x in lines if "step 2 of 2" in x)) - 1].strip() == ""


def test_command_output_is_indented_without_padding_to_console_width():
    console = Console(record=True, width=120)
    handler = ConsoleNodeIOHandler(console)

    handler.show_result("checks", "first line\nsecond line\n", "")

    output = console.export_text()
    assert "  first line\n" in output
    assert "  second line\n" in output
