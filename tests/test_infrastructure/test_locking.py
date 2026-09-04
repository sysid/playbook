from pathlib import Path

import pytest

from playbook.infrastructure.locking import WorkflowLock


def test_workflow_lock_rejects_concurrent_owner(tmp_path: Path):
    lock_path = tmp_path / "daily.lock"

    with WorkflowLock(lock_path):
        with pytest.raises(RuntimeError, match="already running"):
            with WorkflowLock(lock_path):
                pass


def test_workflow_lock_is_released(tmp_path: Path):
    lock_path = tmp_path / "daily.lock"

    with WorkflowLock(lock_path):
        pass

    with WorkflowLock(lock_path):
        pass
