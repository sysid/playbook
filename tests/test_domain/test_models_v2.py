from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from playbook.domain.models import (
    CommandStep,
    RunInfo,
    RunStatus,
    Runbook,
    TriggerType,
)


def test_runbook_whenDefinitionIdentityMissing_thenRejectsIt() -> None:
    with pytest.raises(ValidationError):
        Runbook(id="daily", title="Daily", steps=[])


def test_runInfo_whenDefinitionIdentityMissing_thenRejectsIt() -> None:
    with pytest.raises(ValidationError):
        RunInfo(
            workflow_name="daily",
            run_id=1,
            start_time=datetime.now(timezone.utc),
            status=RunStatus.RUNNING,
            trigger=TriggerType.RUN,
        )


def test_runbook_whenSchemaVersionIsTwo_thenRejectsIt() -> None:
    with pytest.raises(ValidationError):
        Runbook(
            schema_version=2,
            id="daily",
            title="Daily",
            steps=[],
            source_path="/tmp/daily.playbook.toml",
            definition_hash="abc",
        )


def test_step_whenGuardCommandIsGiven_thenKeepsItWithDefaultTimeout() -> None:
    step = CommandStep(
        id="rollback",
        command="./rollback",
        enabled_if_command="test -f /var/run/deploy.lock",
    )

    assert step.enabled_if_command == "test -f /var/run/deploy.lock"
    assert step.enabled_if_timeout_seconds == 30


def test_step_whenGuardCommandIsBlank_thenRejectsIt() -> None:
    with pytest.raises(ValidationError, match="enabled_if_command must not be blank"):
        CommandStep(id="rollback", command="./rollback", enabled_if_command="   ")


def test_step_whenGuardTimeoutIsNotPositive_thenRejectsIt() -> None:
    with pytest.raises(ValidationError):
        CommandStep(
            id="rollback",
            command="./rollback",
            enabled_if_command="true",
            enabled_if_timeout_seconds=0,
        )


def test_step_whenGuardTimeoutHasNoGuardCommand_thenRejectsIt() -> None:
    with pytest.raises(
        ValidationError,
        match="enabled_if_timeout_seconds requires enabled_if_command",
    ):
        CommandStep(id="rollback", command="./rollback", enabled_if_timeout_seconds=10)


def test_step_whenLegacyEnabledIfIsUsed_thenRejectsIt() -> None:
    with pytest.raises(ValidationError):
        CommandStep(id="rollback", command="./rollback", enabled_if="RUN_SECURITY")
