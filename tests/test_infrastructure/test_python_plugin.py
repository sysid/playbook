# tests/test_infrastructure/test_python_plugin.py
"""Tests for the Python plugin."""

import pytest

from src.playbook.infrastructure.plugins.python_plugin import PythonPlugin
from src.playbook.domain.plugins import PluginExecutionError


class TestPythonPlugin:
    """Test cases for the PythonPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create an initialized Python plugin."""
        plugin = PythonPlugin()
        plugin.initialize({})
        return plugin

    def test_get_metadata(self):
        """Test plugin metadata."""
        plugin = PythonPlugin()
        metadata = plugin.get_metadata()

        assert metadata.name == "python"
        assert metadata.version == "1.0.0"
        assert "notify" in metadata.functions
        assert "sleep" in metadata.functions
        assert "throw" in metadata.functions
        assert "call" not in metadata.functions

        notify_func = metadata.functions["notify"]
        assert notify_func.name == "notify"
        assert "message" in notify_func.parameters

    def test_initialize(self):
        """Test plugin initialization."""
        plugin = PythonPlugin()
        plugin.initialize({"some": "config"})

        assert plugin._initialized is True

    def test_execute_invalid_function(self, plugin):
        """Test calling unknown function."""
        with pytest.raises(
            ValueError, match="Function 'invalid' not found in plugin 'python'"
        ):
            plugin.execute("invalid", {})

    def test_execute_uninitialized(self):
        """Test executing on uninitialized plugin."""
        plugin = PythonPlugin()

        with pytest.raises(PluginExecutionError, match="Plugin not initialized"):
            plugin.execute("notify", {"message": "test"})

    def test_execute_notify(self, plugin):
        """Test notify function."""
        result = plugin.execute("notify", {"message": "Test notification"})
        assert result == "Notification sent: Test notification"

    def test_execute_sleep(self, plugin):
        """Test sleep function."""
        result = plugin.execute("sleep", {"seconds": 0})
        assert result == "done"

    def test_execute_throw(self, plugin):
        """Test throw function."""
        with pytest.raises(
            PluginExecutionError, match="Failed to execute function throw"
        ):
            plugin.execute("throw", {})

    def test_cleanup(self, plugin):
        """Test plugin cleanup."""
        plugin.cleanup()
        # Cleanup doesn't do anything for Python plugin, but shouldn't crash

    def test_parameter_validation(self, plugin):
        """Test parameter validation."""
        # Missing required parameter for notify
        with pytest.raises(ValueError, match="Required parameter 'message' missing"):
            plugin.execute("notify", {})

        # Invalid parameter type for sleep
        with pytest.raises(ValueError, match="Cannot convert parameter 'seconds'"):
            plugin.execute("sleep", {"seconds": "not_an_int"})
