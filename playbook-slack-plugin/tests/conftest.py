"""Pytest configuration and fixtures for playbook-slack plugin tests."""

import pytest
from unittest.mock import Mock, patch
from playbook_slack.plugin import SlackPlugin


@pytest.fixture
def slack_plugin():
    """Create a SlackPlugin instance."""
    return SlackPlugin()


@pytest.fixture
def initialized_plugin():
    """Create an initialized SlackPlugin instance with mock configuration."""
    plugin = SlackPlugin()
    plugin.initialize({
        "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
        "bot_token": "xoxb-test-token",
        "default_channel": "#general",
        "timeout": 30,
    })
    return plugin


@pytest.fixture
def webhook_only_plugin():
    """Create a SlackPlugin instance with only webhook configuration."""
    plugin = SlackPlugin()
    plugin.initialize({
        "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
        "timeout": 30,
    })
    return plugin


@pytest.fixture
def bot_token_only_plugin():
    """Create a SlackPlugin instance with only bot token configuration."""
    plugin = SlackPlugin()
    plugin.initialize({
        "bot_token": "xoxb-test-token",
        "default_channel": "#general",
        "timeout": 30,
    })
    return plugin


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch("playbook_slack.plugin.requests") as mock_requests:
        yield mock_requests


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch("playbook_slack.plugin.Path") as mock_path:
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        with patch("builtins.open", create=True) as mock_open:
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            yield mock_path, mock_open, mock_file