"""Integration tests for plugin-backed function steps."""

from datetime import datetime, timezone
from pathlib import Path

from playbook.domain.models import NodeStatus, Runbook
from playbook.infrastructure.persistence import (
    SQLiteNodeExecutionRepository,
    SQLiteRunRepository,
)
from playbook.infrastructure.plugin_registry import PluginRegistry
from playbook.infrastructure.process import ShellProcessRunner
from playbook.service.engine import RunbookEngine
from tests.test_infrastructure.test_plugins.test_plugin import (
    ConfigurableTestPlugin,
    ExampleTestPlugin,
)


class Clock:
    def now(self):
        return datetime.now(timezone.utc)


class RunIO:
    def show_step(self, runbook, step, position, total):
        pass

    def choose(self, prompt, choices):
        assert "run" in choices
        return "run"

    def show_result(self, step_id, stdout, stderr):
        pass


def engine(tmp_path: Path, registry: PluginRegistry) -> RunbookEngine:
    database = tmp_path / "state.db"
    return RunbookEngine(
        clock=Clock(),
        process_runner=ShellProcessRunner(),
        run_repo=SQLiteRunRepository(str(database)),
        node_repo=SQLiteNodeExecutionRepository(str(database)),
        io_handler=RunIO(),
        plugins=registry,
    )


def test_plugin_function_is_executed_and_persisted(tmp_path: Path):
    registry = PluginRegistry()
    registry.register_plugin("test", ExampleTestPlugin)
    workflow = Runbook.model_validate(
        {
            "id": "plugin-test",
            "title": "Plugin Test",
            "source_path": "/runbooks/plugin-test.playbook.toml",
            "definition_hash": "abc",
            "steps": [
                {
                    "id": "echo",
                    "type": "function",
                    "plugin": "test",
                    "function": "echo",
                    "params": {"message": "Hello"},
                }
            ],
        }
    )
    workflow_engine = engine(tmp_path, registry)

    run = workflow_engine.run(workflow)

    executions = workflow_engine.node_repo.get_executions(workflow.id, run.run_id)
    assert executions[0].status == NodeStatus.OK
    assert executions[0].result_text == "Echo: Hello"


def test_plugin_configuration_is_scoped_to_step(tmp_path: Path):
    registry = PluginRegistry()
    registry.register_plugin("configurable", ConfigurableTestPlugin)
    workflow = Runbook.model_validate(
        {
            "id": "plugin-config",
            "title": "Plugin Config",
            "source_path": "/runbooks/plugin-config.playbook.toml",
            "definition_hash": "abc",
            "steps": [
                {
                    "id": "greet",
                    "type": "function",
                    "plugin": "configurable",
                    "function": "greet",
                    "params": {"name": "World"},
                    "config": {"prefix": "Hello"},
                }
            ],
        }
    )
    workflow_engine = engine(tmp_path, registry)

    run = workflow_engine.run(workflow)

    execution = workflow_engine.node_repo.get_executions(
        workflow.id,
        run.run_id,
    )[0]
    assert execution.result_text == "Hello, World!"
