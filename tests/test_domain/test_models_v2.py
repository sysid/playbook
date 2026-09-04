from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from playbook.domain.models import RunInfo, RunStatus, Runbook, TriggerType


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
