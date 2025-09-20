# tests/test_infrastructure/test_plugin_registry.py
"""Tests for the plugin registry."""

import pytest
from unittest.mock import Mock, patch

from src.playbook.infrastructure.plugin_registry import PluginRegistry
from src.playbook.domain.plugins import (
    Plugin,
    PluginMetadata,
    PluginNotFoundError,
    PluginInitializationError,
)
from tests.test_infrastructure.test_plugins.test_plugin import (
    ExampleTestPlugin,
    ConfigurableTestPlugin,
)


class TestPluginRegistry:
    """Test cases for PluginRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh plugin registry."""
        return PluginRegistry()

    def test_register_plugin_success(self, registry):
        """Test successful plugin registration."""
        registry.register_plugin("test", ExampleTestPlugin)

        assert "test" in registry.list_plugins()

    def test_register_plugin_invalid_class(self, registry):
        """Test registering invalid plugin class."""

        class InvalidPlugin:
            pass

        with pytest.raises(ValueError, match="Plugin class must inherit from Plugin"):
            registry.register_plugin("invalid", InvalidPlugin)

    def test_get_plugin_success(self, registry):
        """Test successful plugin retrieval."""
        registry.register_plugin("test", ExampleTestPlugin)

        plugin = registry.get_plugin("test")

        assert isinstance(plugin, ExampleTestPlugin)
        assert plugin._initialized

    def test_get_plugin_with_config(self, registry):
        """Test plugin retrieval with configuration."""
        registry.register_plugin("configurable", ConfigurableTestPlugin)

        plugin = registry.get_plugin("configurable", {"prefix": "Hi"})
        result = plugin.execute("greet", {"name": "World"})

        assert result == "Hi, World!"

    def test_get_plugin_not_found(self, registry):
        """Test retrieving non-existent plugin."""
        with pytest.raises(PluginNotFoundError, match="Plugin 'nonexistent' not found"):
            registry.get_plugin("nonexistent")

    @patch("src.playbook.infrastructure.plugin_registry.logger")
    def test_get_plugin_initialization_error(self, mock_logger, registry):
        """Test plugin initialization error."""

        class FailingPlugin(Plugin):
            def get_metadata(self):
                return PluginMetadata(
                    name="failing", version="1.0.0", author="test", description="test"
                )

            def initialize(self, config):
                raise Exception("Initialization failed")

            def execute(self, function_name, params):
                pass

            def cleanup(self):
                pass

        registry.register_plugin("failing", FailingPlugin)

        with pytest.raises(
            PluginInitializationError, match="Failed to initialize plugin 'failing'"
        ):
            registry.get_plugin("failing")

    def test_get_plugin_cached(self, registry):
        """Test that plugins are cached after first retrieval."""
        registry.register_plugin("test", ExampleTestPlugin)

        plugin1 = registry.get_plugin("test")
        plugin2 = registry.get_plugin("test")

        assert plugin1 is plugin2

    def test_list_plugins(self, registry):
        """Test listing available plugins."""
        registry.register_plugin("test1", ExampleTestPlugin)
        registry.register_plugin("test2", ConfigurableTestPlugin)

        plugins = registry.list_plugins()

        assert "test1" in plugins
        assert "test2" in plugins
        assert len(plugins) == 2

    def test_get_plugin_metadata(self, registry):
        """Test getting plugin metadata without initialization."""
        registry.register_plugin("test", ExampleTestPlugin)

        metadata = registry.get_plugin_metadata("test")

        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert "echo" in metadata.functions

    def test_get_plugin_metadata_not_found(self, registry):
        """Test getting metadata for non-existent plugin."""
        with pytest.raises(PluginNotFoundError):
            registry.get_plugin_metadata("nonexistent")

    def test_cleanup_all(self, registry):
        """Test cleaning up all plugins."""
        registry.register_plugin("test", ExampleTestPlugin)
        plugin = registry.get_plugin("test")

        # Verify plugin is initialized
        assert plugin._initialized

        registry.cleanup_all()

        # Plugin should be cleaned up
        assert not plugin._initialized

    def test_reload_plugin(self, registry):
        """Test reloading a plugin."""
        registry.register_plugin("configurable", ConfigurableTestPlugin)

        # Get plugin with one config
        plugin1 = registry.get_plugin("configurable", {"prefix": "Hello"})
        result1 = plugin1.execute("greet", {"name": "World"})
        assert result1 == "Hello, World!"

        # Reload with different config
        plugin2 = registry.reload_plugin("configurable", {"prefix": "Hi"})
        result2 = plugin2.execute("greet", {"name": "World"})
        assert result2 == "Hi, World!"

        # Should be different instances
        assert plugin1 is not plugin2

    def test_get_plugin_info(self, registry):
        """Test getting information about all plugins."""
        registry.register_plugin("test", ExampleTestPlugin)
        registry.register_plugin("configurable", ConfigurableTestPlugin)

        # Initialize one plugin
        registry.get_plugin("test")

        info = registry.get_plugin_info()

        assert len(info) == 2

        # Find test plugin info
        test_info = next(p for p in info if p["name"] == "test")
        assert test_info["version"] == "1.0.0"
        assert test_info["initialized"] is True
        assert "echo" in test_info["functions"]

        # Find configurable plugin info
        config_info = next(p for p in info if p["name"] == "configurable")
        assert config_info["initialized"] is False

    @patch("src.playbook.infrastructure.plugin_registry.entry_points")
    def test_discover_entry_point_plugins(self, mock_entry_points, registry):
        """Test discovering plugins through entry points."""
        # Mock entry point
        mock_entry_point = Mock()
        mock_entry_point.name = "test_plugin"
        mock_entry_point.load.return_value = ExampleTestPlugin

        # Mock entry_points() response for Python 3.10+ style
        mock_eps = Mock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        registry.discover_plugins()

        assert "test_plugin" in registry.list_plugins()

    @patch("src.playbook.infrastructure.plugin_registry.entry_points")
    @patch("src.playbook.infrastructure.plugin_registry.logger")
    def test_discover_entry_point_plugins_load_error(
        self, mock_logger, mock_entry_points, registry
    ):
        """Test handling errors during entry point loading."""
        # Mock entry point that fails to load
        mock_entry_point = Mock()
        mock_entry_point.name = "failing_plugin"
        mock_entry_point.load.side_effect = Exception("Load failed")

        mock_eps = Mock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        registry.discover_plugins()

        # Should not crash, but should log error
        mock_logger.error.assert_called()
        assert "failing_plugin" not in registry.list_plugins()

    def test_discover_plugins_only_once(self, registry):
        """Test that plugin discovery only happens once."""
        registry.register_plugin("test", ExampleTestPlugin)

        # First discovery
        registry.discover_plugins()
        registry.list_plugins()

        # Register another plugin after discovery - this should still work
        registry.register_plugin("test2", ConfigurableTestPlugin)

        # Second discovery should not re-run entry point discovery
        # but manual registrations should still be available
        registry.discover_plugins()
        plugins2 = registry.list_plugins()

        # Manual registration after discovery should still work
        assert "test" in plugins2
        assert "test2" in plugins2
        assert len(plugins2) == 2
