# tests/test_domain/test_plugin_models.py
"""Tests for plugin-related domain models."""

import pytest
from pydantic import ValidationError

from src.playbook.domain.models import FunctionNode, NodeType


class TestFunctionNodePluginSupport:
    """Test FunctionNode plugin-only support."""

    def test_function_node_plugin_mode(self):
        """Test FunctionNode with plugin-based execution."""
        node = FunctionNode(
            id="test",
            name="Test Node",
            plugin="slack",
            function="send_message",
            function_params={"channel": "#test", "message": "Hello"},
            plugin_config={"webhook_url": "https://hooks.slack.com/..."},
            depends_on=[],
        )

        assert node.plugin == "slack"
        assert node.function == "send_message"
        assert node.function_params == {"channel": "#test", "message": "Hello"}
        assert node.plugin_config == {"webhook_url": "https://hooks.slack.com/..."}

    def test_function_node_missing_plugin(self):
        """Test FunctionNode validation when plugin is missing."""
        with pytest.raises(ValidationError):
            FunctionNode(
                id="test", name="Test Node", function="send_message", depends_on=[]
            )

    def test_function_node_missing_function(self):
        """Test FunctionNode validation when function is missing."""
        with pytest.raises(ValidationError):
            FunctionNode(id="test", name="Test Node", plugin="slack", depends_on=[])

    def test_function_node_missing_both(self):
        """Test FunctionNode validation when both plugin and function are missing."""
        with pytest.raises(ValidationError):
            FunctionNode(id="test", name="Test Node", depends_on=[])

    def test_function_node_defaults(self):
        """Test FunctionNode defaults."""
        node = FunctionNode(
            id="test",
            name="Test Node",
            plugin="python",
            function="notify",
            depends_on=[],
        )

        assert node.function_params == {}
        assert node.plugin_config == {}
        assert node.type == NodeType.FUNCTION
        assert node.critical is False  # From BaseNode
        assert node.skip is False  # From BaseNode

    def test_function_node_python_plugin_built_ins(self):
        """Test FunctionNode with Python plugin built-in functions."""
        # Test notify function
        notify_node = FunctionNode(
            id="notify_test",
            name="Notify Test",
            plugin="python",
            function="notify",
            function_params={"message": "Test notification"},
            depends_on=[],
        )

        assert notify_node.plugin == "python"
        assert notify_node.function == "notify"
        assert notify_node.function_params == {"message": "Test notification"}

        # Test sleep function
        sleep_node = FunctionNode(
            id="sleep_test",
            name="Sleep Test",
            plugin="python",
            function="sleep",
            function_params={"seconds": 5},
            depends_on=[],
        )

        assert sleep_node.plugin == "python"
        assert sleep_node.function == "sleep"
        assert sleep_node.function_params == {"seconds": 5}

    def test_function_node_python_plugin_throw_function(self):
        """Test FunctionNode with Python plugin throw function."""
        node = FunctionNode(
            id="throw_test",
            name="Throw Test",
            plugin="python",
            function="throw",
            function_params={},
            depends_on=[],
        )

        assert node.plugin == "python"
        assert node.function == "throw"
        assert node.function_params == {}
