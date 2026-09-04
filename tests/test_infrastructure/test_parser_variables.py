"""Variable rendering through the schema-v2 parser."""

from pathlib import Path

import pytest

from playbook.infrastructure.parser import RunbookParser
from playbook.infrastructure.variables import VariableManager, VariableValidationError


def write_runbook(path: Path, variables: str, steps: str) -> Path:
    path.write_text(
        f"""
schema_version = 2

[variables]
{variables}

[runbook]
id = "deploy"
title = "Deploy {{{{ APP_NAME }}}}"

{steps}
"""
    )
    return path


def parser() -> RunbookParser:
    return RunbookParser(VariableManager(interactive=False))


def test_variables_are_rendered_recursively(tmp_path: Path):
    path = write_runbook(
        tmp_path / "deploy.playbook.toml",
        'APP_NAME = { default = "myapp" }\nTIMEOUT = { default = 60, type = "int" }',
        """
[[steps]]
id = "notify"
type = "function"
plugin = "python"
function = "notify"
params = { message = "Deploying {{ APP_NAME }}", timeout = "{{ TIMEOUT }}" }
""",
    )

    runbook = parser().parse(path, {"APP_NAME": "service", "TIMEOUT": "90"})

    assert runbook.title == "Deploy service"
    assert runbook.variables == {"APP_NAME": "service", "TIMEOUT": 90}
    assert runbook.steps[0].params == {
        "message": "Deploying service",
        "timeout": "90",
    }


def test_defaults_are_used(tmp_path: Path):
    path = write_runbook(
        tmp_path / "deploy.playbook.toml",
        'APP_NAME = { default = "myapp" }',
        """
[[steps]]
id = "review"
type = "manual"
instructions = "Review {{ APP_NAME }}"
""",
    )

    runbook = parser().parse(path)

    assert runbook.title == "Deploy myapp"
    assert runbook.steps[0].instructions == "Review myapp"


def test_missing_required_variable_fails(tmp_path: Path):
    path = write_runbook(
        tmp_path / "deploy.playbook.toml",
        "APP_NAME = { required = true }",
        """
[[steps]]
id = "review"
type = "manual"
instructions = "Review {{ APP_NAME }}"
""",
    )

    with pytest.raises(VariableValidationError, match="Required variable"):
        parser().parse(path)


def test_invalid_choice_fails(tmp_path: Path):
    path = write_runbook(
        tmp_path / "deploy.playbook.toml",
        'APP_NAME = { choices = ["dev", "prod"] }',
        """
[[steps]]
id = "review"
type = "manual"
instructions = "Review"
""",
    )

    with pytest.raises(VariableValidationError, match="not in allowed choices"):
        parser().parse(path, {"APP_NAME": "other"})


def test_get_variable_definitions_returns_v2_definitions(tmp_path: Path):
    path = write_runbook(
        tmp_path / "deploy.playbook.toml",
        'APP_NAME = { default = "myapp", secret = true }',
        """
[[steps]]
id = "review"
type = "manual"
instructions = "Review"
""",
    )

    definitions = parser().get_variable_definitions(path)

    assert definitions["APP_NAME"].default == "myapp"
    assert definitions["APP_NAME"].secret is True
