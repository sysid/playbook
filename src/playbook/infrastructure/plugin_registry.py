# src/playbook/infrastructure/plugin_registry.py
"""Plugin registry for discovering and managing plugins."""

import logging
from typing import Dict, List, Type, Optional
from importlib.metadata import entry_points

from ..domain.plugins import (
    Plugin,
    PluginMetadata,
    PluginError,
    PluginNotFoundError,
    PluginInitializationError,
)

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for discovering and managing plugins."""

    ENTRY_POINT_GROUP = "playbook.plugins"

    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
        self._initialized = False

    def discover_plugins(self) -> None:
        """Discover plugins through entry points and manual registration."""
        if self._initialized:
            return

        logger.info("Discovering plugins...")
        self._discover_entry_point_plugins()
        self._initialized = True
        logger.info(f"Discovered {len(self._plugin_classes)} plugins")

    def _discover_entry_point_plugins(self) -> None:
        """Discover plugins through setuptools entry points."""
        try:
            eps = entry_points()
            if hasattr(eps, "select"):  # Python 3.10+
                plugin_entries = eps.select(group=self.ENTRY_POINT_GROUP)
            else:  # Python 3.9
                plugin_entries = eps.get(self.ENTRY_POINT_GROUP, [])

            for entry_point in plugin_entries:
                try:
                    plugin_class = entry_point.load()
                    if not issubclass(plugin_class, Plugin):
                        logger.warning(
                            f"Entry point {entry_point.name} does not implement Plugin interface"
                        )
                        continue

                    self._plugin_classes[entry_point.name] = plugin_class
                    logger.debug(f"Discovered plugin: {entry_point.name}")

                except Exception as e:
                    logger.error(f"Failed to load plugin {entry_point.name}: {e}")

        except Exception as e:
            logger.warning(f"Failed to discover entry point plugins: {e}")

    def register_plugin(self, name: str, plugin_class: Type[Plugin]) -> None:
        """Manually register a plugin class.

        Args:
            name: Plugin name
            plugin_class: Plugin class to register

        Raises:
            ValueError: If plugin class is invalid
        """
        if not issubclass(plugin_class, Plugin):
            raise ValueError("Plugin class must inherit from Plugin")

        self._plugin_classes[name] = plugin_class
        logger.debug(f"Manually registered plugin: {name}")

    def get_plugin(self, name: str, config: Optional[Dict] = None) -> Plugin:
        """Get a plugin instance by name.

        Args:
            name: Plugin name
            config: Plugin configuration

        Returns:
            Initialized plugin instance

        Raises:
            PluginNotFoundError: If plugin not found
            PluginInitializationError: If plugin initialization fails
        """
        if not self._initialized:
            self.discover_plugins()

        # Return cached instance if available
        if name in self._plugins:
            return self._plugins[name]

        # Create new instance
        if name not in self._plugin_classes:
            raise PluginNotFoundError(f"Plugin '{name}' not found")

        try:
            plugin_class = self._plugin_classes[name]
            plugin_instance = plugin_class()

            # Initialize with config
            plugin_instance.initialize(config or {})

            # Cache the instance
            self._plugins[name] = plugin_instance
            logger.debug(f"Initialized plugin: {name}")

            return plugin_instance

        except Exception as e:
            raise PluginInitializationError(
                f"Failed to initialize plugin '{name}': {e}"
            )

    def list_plugins(self) -> List[str]:
        """Get list of available plugin names.

        Returns:
            List of plugin names
        """
        if not self._initialized:
            self.discover_plugins()

        return list(self._plugin_classes.keys())

    def get_plugin_metadata(self, name: str) -> PluginMetadata:
        """Get metadata for a plugin without initializing it.

        Args:
            name: Plugin name

        Returns:
            Plugin metadata

        Raises:
            PluginNotFoundError: If plugin not found
            PluginError: If metadata cannot be retrieved
        """
        if not self._initialized:
            self.discover_plugins()

        if name not in self._plugin_classes:
            raise PluginNotFoundError(f"Plugin '{name}' not found")

        try:
            # Create temporary instance just to get metadata
            plugin_class = self._plugin_classes[name]
            temp_instance = plugin_class()
            return temp_instance.get_metadata()
        except Exception as e:
            raise PluginError(f"Failed to get metadata for plugin '{name}': {e}")

    def cleanup_all(self) -> None:
        """Clean up all initialized plugins."""
        for name, plugin in self._plugins.items():
            try:
                plugin.cleanup()
                logger.debug(f"Cleaned up plugin: {name}")
            except Exception as e:
                logger.error(f"Failed to cleanup plugin {name}: {e}")

        self._plugins.clear()

    def reload_plugin(self, name: str, config: Optional[Dict] = None) -> Plugin:
        """Reload a plugin instance.

        Args:
            name: Plugin name
            config: Plugin configuration

        Returns:
            Reloaded plugin instance

        Raises:
            PluginNotFoundError: If plugin not found
        """
        # Cleanup existing instance
        if name in self._plugins:
            try:
                self._plugins[name].cleanup()
            except Exception as e:
                logger.warning(f"Failed to cleanup plugin {name} during reload: {e}")
            del self._plugins[name]

        # Get fresh instance
        return self.get_plugin(name, config)

    def get_plugin_info(self) -> List[Dict]:
        """Get information about all available plugins.

        Returns:
            List of plugin information dictionaries
        """
        if not self._initialized:
            self.discover_plugins()

        plugin_info = []
        for name in self._plugin_classes:
            try:
                metadata = self.get_plugin_metadata(name)
                info = {
                    "name": name,
                    "version": metadata.version,
                    "author": metadata.author,
                    "description": metadata.description,
                    "functions": list(metadata.functions.keys()),
                    "initialized": name in self._plugins,
                }
                plugin_info.append(info)
            except Exception as e:
                plugin_info.append(
                    {"name": name, "error": str(e), "initialized": False}
                )

        return plugin_info


# Global plugin registry instance
plugin_registry = PluginRegistry()
