from pathlib import Path

import pytest
import tomllib

from playbook.infrastructure.migration import LegacyRunbookMigrator
from playbook.infrastructure.parser import RunbookParser


def write_legacy_runbook(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "legacy.playbook.toml"
    path.write_text(content)
    return path


def test_migrate_whenLinearLegacyRunbook_thenProducesOrderedVersionTwo(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Daily"
description = "Daily routine"
version = "1.0"
author = "Tom"
created_at = "2025-01-01T00:00:00"

[login]
type = "Manual"
description = "Log in."
critical = true
depends_on = []

[check]
type = "Command"
command_name = "true"
depends_on = ["login"]
""",
    )

    migrated = LegacyRunbookMigrator().migrate(path)
    data = tomllib.loads(migrated)

    assert data["schema_version"] == 2
    assert data["runbook"]["id"] == "legacy"
    assert [step["id"] for step in data["steps"]] == ["login", "check"]
    assert data["steps"][0]["type"] == "manual"
    assert data["steps"][0]["required"] is True
    assert data["steps"][1]["type"] == "command"
    assert data["steps"][1]["command"] == "true"


def test_migrate_whenSimpleBooleanCondition_thenUsesEnabledIf(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Checks"
description = "Optional checks"
version = "1.0"
author = "Tom"
created_at = "2025-01-01T00:00:00"

[variables.RUN_SECURITY]
type = "bool"
default = false

[security]
type = "Command"
command_name = "true"
depends_on = []
when = "{{ RUN_SECURITY }}"
""",
    )

    migrated = tomllib.loads(LegacyRunbookMigrator().migrate(path))

    assert migrated["steps"][0]["enabled_if"] == "RUN_SECURITY"


def test_migrate_whenConditionIsComplex_thenFailsWithStepContext(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Deploy"
description = "Deploy"
version = "1.0"
author = "Tom"
created_at = "2025-01-01T00:00:00"

[deploy]
type = "Command"
command_name = "true"
depends_on = []
when = "{{ ENVIRONMENT == 'prod' }}"
""",
    )

    with pytest.raises(
        ValueError,
        match=r"step 'deploy'.*cannot migrate complex condition",
    ):
        LegacyRunbookMigrator().migrate(path)


def test_migrate_converts_function_configuration_and_disabled_step(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Notify"

[notify]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = { text = "done" }
plugin_config = { channel = "ops" }
prompt_after = "Message received?"
skip = true
depends_on = []
""",
    )

    step = tomllib.loads(LegacyRunbookMigrator().migrate(path))["steps"][0]

    assert step == {
        "id": "notify",
        "type": "function",
        "required": False,
        "enabled": False,
        "plugin": "slack",
        "function": "send_message",
        "params": {"text": "done"},
        "config": {"channel": "ops"},
        "verify": "Message received?",
    }


def test_migrate_expands_dependency_shortcuts_in_stable_order(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Shortcuts"

[first]
type = "Manual"
description = "First"
depends_on = []

[second]
type = "Manual"
description = "Second"
depends_on = "^"

[third]
type = "Manual"
description = "Third"
depends_on = ["*"]
""",
    )

    data = tomllib.loads(LegacyRunbookMigrator().migrate(path))

    assert [step["id"] for step in data["steps"]] == [
        "first",
        "second",
        "third",
    ]
    assert not any(step["required"] for step in data["steps"])


@pytest.mark.parametrize(
    ("node", "message"),
    [
        (
            'type = "Command"\ncommand_name = "true"\ndepends_on = 3',
            "depends_on must be a string or list",
        ),
        (
            'type = "Command"\ncommand_name = "true"\ndepends_on = [3]',
            "dependencies must be strings",
        ),
        (
            'type = "Command"\ncommand_name = "true"\ndepends_on = ["missing"]',
            "unknown dependencies",
        ),
        (
            'type = "Command"\ncommand_name = "true"\ndepends_on = ["other:success"]',
            "cannot migrate conditional dependency",
        ),
        ('type = "Command"\ndepends_on = []', "command_name is required"),
        ('type = "Function"\ndepends_on = []', "plugin and function are required"),
        ('type = "Unknown"\ndepends_on = []', "unknown type"),
    ],
)
def test_migrate_rejects_legacy_shapes_that_have_no_safe_v2_mapping(
    tmp_path: Path,
    node: str,
    message: str,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        f"""
[runbook]
title = "Invalid"

[step]
{node}
""",
    )

    with pytest.raises(ValueError, match=message):
        LegacyRunbookMigrator().migrate(path)


def test_migrate_rejects_dependency_cycles(tmp_path: Path) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Cycle"

[one]
type = "Manual"
depends_on = ["two"]

[two]
type = "Manual"
depends_on = ["one"]
""",
    )

    with pytest.raises(ValueError, match="dependency cycle"):
        LegacyRunbookMigrator().migrate(path)


def test_migrate_rejects_v2_and_missing_metadata(tmp_path: Path) -> None:
    v2 = write_legacy_runbook(tmp_path, "schema_version = 2")
    with pytest.raises(ValueError, match="already uses schema version 2"):
        LegacyRunbookMigrator().migrate(v2)

    v2.write_text('[step]\ntype = "Manual"')
    with pytest.raises(ValueError, match=r"missing \[runbook\]"):
        LegacyRunbookMigrator().migrate(v2)


def test_migrate_whenManualNodeHasNoDescription_thenNamesEveryOffendingStep(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Daily"

[login]
type = "Manual"
description = "Log in to the corporate VPN."
depends_on = []

[login-aws]
type = "Manual"
prompt_after = "Do you have a valid AWS cli session?"
depends_on = ["login"]

[alarms]
type = "Manual"
prompt_after = "Ready?"
depends_on = ["login"]
""",
    )

    with pytest.raises(ValueError) as error:
        LegacyRunbookMigrator().migrate(path)

    message = str(error.value)
    assert "login-aws" in message
    assert "alarms" in message
    assert "login" not in message.replace("login-aws", "")


def test_migrate_whenNodeIsOnlyADependency_thenItStaysSkippable(
    tmp_path: Path,
) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Daily"

[gate]
type = "Manual"
description = "Authorise the run."
critical = true
depends_on = []

[warmup]
type = "Manual"
description = "Warm up the cache."
depends_on = ["gate"]

[report]
type = "Manual"
description = "Write the report."
depends_on = ["warmup"]
""",
    )

    data = tomllib.loads(LegacyRunbookMigrator().migrate(path))
    required = {step["id"]: step["required"] for step in data["steps"]}

    assert required == {"gate": True, "warmup": False, "report": False}


def test_migrate_output_is_always_a_valid_v2_runbook(tmp_path: Path) -> None:
    path = write_legacy_runbook(
        tmp_path,
        """
[runbook]
title = "Daily"

[login]
type = "Manual"
description = "Log in."
critical = true
depends_on = []

[checks]
type = "Command"
command_name = "true"
prompt_after = "All green?"
depends_on = ["login"]
""",
    )

    output = tmp_path / "daily.v2.playbook.toml"
    LegacyRunbookMigrator().migrate_to(path, output)

    RunbookParser().parse(output)
