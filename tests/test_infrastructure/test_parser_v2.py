from pathlib import Path

import pytest

from playbook.domain.models import CommandStep, ManualStep
from playbook.infrastructure.parser import RunbookParser


def write_runbook(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "example.playbook.toml"
    path.write_text(content)
    return path


def test_parse_whenOrderedSteps_thenPreservesFileOrder(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 2

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
schema_version = 2

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


def test_parse_whenVersionOneInput_thenPointsToMigrator(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
[runbook]
title = "Legacy"
description = "Old format"
version = "1"
author = "Tom"
created_at = "2025-01-01T00:00:00"

[first]
type = "Manual"
""",
    )

    with pytest.raises(ValueError, match=r"playbook migrate"):
        RunbookParser().parse(path)


def test_parse_whenEnabledIfReferencesSecret_thenRejectsRunbook(
    tmp_path: Path,
) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 2

[runbook]
id = "daily"
title = "Daily"

[variables.RUN_SECURITY]
type = "bool"
default = false
secret = true

[[steps]]
id = "security"
type = "command"
command = "true"
enabled_if = "RUN_SECURITY"
""",
    )

    with pytest.raises(ValueError, match="cannot reference secret variable"):
        RunbookParser().parse(path)


def test_parse_whenEnabledIfIsNotBoolean_thenRejectsRunbook(tmp_path: Path) -> None:
    path = write_runbook(
        tmp_path,
        """
schema_version = 2

[runbook]
id = "daily"
title = "Daily"

[variables.ENVIRONMENT]
type = "string"
default = "test"

[[steps]]
id = "deploy"
type = "command"
command = "true"
enabled_if = "ENVIRONMENT"
""",
    )

    with pytest.raises(ValueError, match="must reference a bool variable"):
        RunbookParser().parse(path)


def test_parse_rejects_wrong_extension_and_invalid_toml(tmp_path: Path) -> None:
    wrong_extension = tmp_path / "workflow.toml"
    wrong_extension.write_text("schema_version = 2")
    with pytest.raises(ValueError, match=r"\.playbook\.toml extension"):
        RunbookParser().parse(wrong_extension)

    invalid = write_runbook(tmp_path, "not = [valid")
    with pytest.raises(ValueError, match="Cannot parse runbook TOML"):
        RunbookParser().parse(invalid)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("schema_version = 2\nsteps = []", r"Missing required \[runbook\]"),
        (
            'schema_version = 2\n[runbook]\nid = "x"\ntitle = "X"',
            r"Missing required \[\[steps\]\]",
        ),
        (
            'schema_version = 2\nvariables = []\n[runbook]\nid = "x"\ntitle = "X"\nsteps = []',
            r"\[variables\] must be a table",
        ),
    ],
)
def test_parse_reports_missing_v2_structure(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = write_runbook(tmp_path, content)

    with pytest.raises(ValueError, match=message):
        RunbookParser().parse(path)


def test_parse_rejects_enabled_if_unknown_variable(tmp_path: Path) -> None:
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
enabled_if = "UNKNOWN"
""",
    )

    with pytest.raises(ValueError, match="references unknown variable"):
        RunbookParser().parse(path)
