from typing import Any

import pytest

from playbook.domain.plugins import Plugin, PluginMetadata
from playbook.infrastructure.plugin_registry import PluginRegistry


class ConfiguredPlugin(Plugin):
    initialized_configs: list[dict[str, Any]] = []

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="configured",
            version="1",
            author="test",
            description="test",
        )

    def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized_configs.append(config)

    def execute(self, function_name: str, params: dict[str, Any]) -> Any:
        return self.config

    def cleanup(self) -> None:
        pass


def test_getPlugin_whenConfigurationsDiffer_thenReturnsIsolatedInstances() -> None:
    ConfiguredPlugin.initialized_configs = []
    registry = PluginRegistry()
    registry.register_plugin("configured", ConfiguredPlugin)

    first = registry.get_plugin("configured", {"value": "first"})
    second = registry.get_plugin("configured", {"value": "second"})

    assert first is not second
    assert first.config == {"value": "first"}
    assert second.config == {"value": "second"}


def test_registerPlugin_whenNameHasDifferentImplementation_thenRejectsDuplicate() -> (
    None
):
    class OtherPlugin(ConfiguredPlugin):
        pass

    registry = PluginRegistry()
    registry.register_plugin("configured", ConfiguredPlugin)

    with pytest.raises(ValueError, match="already registered"):
        registry.register_plugin("configured", OtherPlugin)
