from pathlib import Path

import pytest

from playbook.domain.models import CommandStep, ManualStep
from playbook.infrastructure.parser import RunbookParser
from playbook.infrastructure.variables import VariableManager


def write_runbook(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "example.playbook.toml"
    path.write_text(content)
    return path


def test_parse_whenOrderedSteps_thenPreservesFileOrder(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 3

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "login"
type = "manual"
instructions = "Log in."

[[steps]]
id = "check"
type = "command"
command = "true"
required = false
""",
    )

    runbook = RunbookParser().parse(path)

    assert runbook.id == "daily"
    assert [step.id for step in runbook.steps] == ["login", "check"]
    assert isinstance(runbook.steps[0], ManualStep)
    assert isinstance(runbook.steps[1], CommandStep)
    assert runbook.steps[0].required is True
    assert runbook.steps[1].required is False


def test_parse_whenDuplicateStepId_thenRejectsRunbook(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 3

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "same"
type = "manual"
instructions = "First."

[[steps]]
id = "same"
type = "manual"
instructions = "Second."
""",
    )

    with pytest.raises(ValueError, match="Duplicate step id 'same'"):
        RunbookParser().parse(path)


def test_parse_whenSchemaVersionIsTwo_thenNamesTheReplacementField(
    tmp_path: Path,
) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 2

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "check"
type = "command"
command = "true"
enabled_if = "RUN_SECURITY"
""",
    )

    with pytest.raises(ValueError, match="enabled_if_command"):
        RunbookParser().parse(path)


def test_parse_whenSchemaVersionIsMissing_thenReportsRequiredVersion(
    tmp_path: Path,
) -> None:
    path = write_runbook(
        tmp_path,
        """
[runbook]
title = "Legacy"
version = "1"

[first]
type = "Manual"
""",
    )

    with pytest.raises(ValueError, match="schema_version = 3"):
        RunbookParser().parse(path)


def test_parse_whenStepIsGuarded_thenKeepsCommandAndTimeout(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 3

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "rollback"
type = "command"
command = "./rollback"
enabled_if_command = "test -f /var/run/deploy.lock"
enabled_if_timeout_seconds = 5
""",
    )

    runbook = RunbookParser().parse(path)

    assert runbook.steps[0].enabled_if_command == "test -f /var/run/deploy.lock"
    assert runbook.steps[0].enabled_if_timeout_seconds == 5


def test_parse_whenGuardUsesVariable_thenSubstitutesIt(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 3

[variables]
LOCK_FILE = { default = "/var/run/deploy.lock" }

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "rollback"
type = "command"
command = "./rollback"
enabled_if_command = "test -f {{ LOCK_FILE }}"
""",
    )

    runbook = RunbookParser(VariableManager(interactive=False)).parse(path)

    assert runbook.steps[0].enabled_if_command == "test -f /var/run/deploy.lock"


def test_parse_whenGuardComparesBoolean_thenRendersPythonCapitalisation(
    tmp_path: Path,
) -> None:
    """A rendered bool is 'True', not 'true'; guards must compare against that."""
    path = write_runbook(
        tmp_path,
        """
schema_version = 3

[variables]
RUN_SECURITY = { type = "bool", default = true }

[runbook]
id = "daily"
title = "Daily"

[[steps]]
id = "security"
type = "command"
command = "./security-review"
enabled_if_command = "test '{{ RUN_SECURITY }}' = 'True'"
""",
    )

    runbook = RunbookParser(VariableManager(interactive=False)).parse(path)

    assert runbook.steps[0].enabled_if_command == "test 'True' = 'True'"


def test_parse_rejects_wrong_extension_and_invalid_toml(tmp_path: Path) -> None:
    wrong_extension = tmp_path / "workflow.toml"
    wrong_extension.write_text("schema_version = 3")
    with pytest.raises(ValueError, match=r"\.playbook\.toml extension"):
        RunbookParser().parse(wrong_extension)

    invalid = write_runbook(tmp_path, "not = [valid")
    with pytest.raises(ValueError, match="Cannot parse runbook TOML"):
        RunbookParser().parse(invalid)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("schema_version = 3\nsteps = []", r"Missing required \[runbook\]"),
        (
            'schema_version = 3\n[runbook]\nid = "x"\ntitle = "X"',
            r"Missing required \[\[steps\]\]",
        ),
        (
            'schema_version = 3\nvariables = []\n[runbook]\nid = "x"\ntitle = "X"\nsteps = []',
            r"\[variables\] must be a table",
        ),
    ],
)
def test_parse_reports_missing_structure(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = write_runbook(tmp_path, content)

    with pytest.raises(ValueError, match=message):
        RunbookParser().parse(path)


def test_parse_rejects_unknown_step_field(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 3
[runbook]
id = "daily"
title = "Daily"
[[steps]]
id = "check"
type = "command"
command = "true"
enabled_if = "UNKNOWN"
""",
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        RunbookParser().parse(path)
