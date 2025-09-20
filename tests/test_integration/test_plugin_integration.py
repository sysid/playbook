# tests/test_integration/test_plugin_integration.py
"""Integration tests for the plugin system."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.playbook.infrastructure.parser import RunbookParser
from src.playbook.infrastructure.variables import VariableManager
from src.playbook.service.engine import RunbookEngine
from src.playbook.domain.models import NodeStatus
from src.playbook.infrastructure.persistence import SQLiteRunRepository, SQLiteNodeExecutionRepository
from src.playbook.infrastructure.process import ShellProcessRunner
from tests.test_infrastructure.test_plugins.test_plugin import ExampleTestPlugin


class TestPluginIntegration:
    """Integration tests for the complete plugin workflow."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def engine_with_plugins(self, temp_db_path):
        """Create a RunbookEngine with plugin support."""
        # Mock dependencies
        clock = Mock()
        now_time = datetime.now()
        clock.now.return_value = now_time

        process_runner = ShellProcessRunner()
        run_repo = SQLiteRunRepository(temp_db_path)
        node_repo = SQLiteNodeExecutionRepository(temp_db_path)
        io_handler = Mock()

        # Create engine (this will initialize plugins)
        engine = RunbookEngine(
            clock=clock,
            process_runner=process_runner,
            run_repo=run_repo,
            node_repo=node_repo,
            io_handler=io_handler
        )

        return engine, io_handler

    def test_plugin_based_function_execution(self, engine_with_plugins, temp_db_path):
        """Test executing a function using the plugin system."""
        engine, io_handler = engine_with_plugins

        # Register our test plugin
        from src.playbook.infrastructure.plugin_registry import plugin_registry
        plugin_registry.register_plugin("test", ExampleTestPlugin)

        # Create a runbook with plugin-based function
        runbook_toml = """
[runbook]
title = "Plugin Test Workflow"
description = "Test plugin-based function execution"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[test_function]
type = "Function"
plugin = "test"
function = "echo"
function_params = { message = "Hello from plugin!" }
description = "Test plugin function"
depends_on = []
"""

        # Parse the runbook
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(runbook_toml)
            f.flush()

            parser = RunbookParser(VariableManager())
            runbook = parser.parse(f.name, variables={})

        # Execute the workflow
        run_info = engine.start_run(runbook)
        engine.execute_node(runbook, "test_function", run_info)

        # Verify the function was executed correctly
        node_executions = engine.node_repo.get_executions(runbook.title, run_info.run_id)
        assert len(node_executions) == 1

        execution = node_executions[0]
        assert execution.node_id == "test_function"
        assert execution.status == NodeStatus.OK
        assert execution.result_text == "Echo: Hello from plugin!"


    def test_plugin_with_configuration(self, engine_with_plugins, temp_db_path):
        """Test plugin execution with configuration."""
        engine, io_handler = engine_with_plugins

        # Register our configurable test plugin
        from tests.test_infrastructure.test_plugins.test_plugin import ConfigurableTestPlugin
        from src.playbook.infrastructure.plugin_registry import plugin_registry
        plugin_registry.register_plugin("configurable", ConfigurableTestPlugin)

        # Create a runbook with plugin configuration
        runbook_toml = """
[runbook]
title = "Plugin Config Test"
description = "Test plugin with configuration"
version = "1.0.0"
author = "test"
created_at = "2025-01-20T12:00:00Z"

[greeting]
type = "Function"
plugin = "configurable"
function = "greet"
function_params = { name = "World" }
plugin_config = { prefix = "Hello" }
description = "Test configured plugin function"
depends_on = []
"""

        # Parse the runbook
        with tempfile.NamedTemporaryFile(mode='w', suffix='.playbook.toml', delete=False) as f:
            f.write(runbook_toml)
            f.flush()

            parser = RunbookParser(VariableManager())
            runbook = parser.parse(f.name, variables={})

        # Execute the workflow
        run_info = engine.start_run(runbook)
        engine.execute_node(runbook, "greeting", run_info)

        # Verify the function was executed correctly with config
        node_executions = engine.node_repo.get_executions(runbook.title, run_info.run_id)
        assert len(node_executions) == 1

        execution = node_executions[0]
        assert execution.node_id == "greeting"
        assert execution.status == NodeStatus.OK
        assert execution.result_text == "Hello, World!"