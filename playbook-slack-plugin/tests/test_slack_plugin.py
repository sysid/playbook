"""Comprehensive tests for SlackPlugin."""

import json
from unittest.mock import Mock, patch
from pathlib import Path

import pytest
import requests
from playbook.domain.plugins import (
    PluginInitializationError,
    PluginExecutionError,
)

from playbook_slack.plugin import SlackPlugin


class TestSlackPluginMetadata:
    """Test SlackPlugin metadata functionality."""

    def test_get_metadata(self, slack_plugin):
        """Test plugin metadata retrieval."""
        metadata = slack_plugin.get_metadata()

        assert metadata.name == "slack"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Playbook Community"
        assert "Slack integration" in metadata.description

        # Check functions
        assert "send_message" in metadata.functions
        assert "send_file" in metadata.functions
        assert "create_channel" in metadata.functions

        # Check function parameters
        send_message_func = metadata.functions["send_message"]
        assert send_message_func.parameters["text"].required is True
        assert send_message_func.parameters["channel"].required is False
        assert send_message_func.parameters["urgency"].choices == ["low", "normal", "high", "critical"]


class TestSlackPluginInitialization:
    """Test SlackPlugin initialization."""

    def test_initialize_with_webhook_url(self, slack_plugin):
        """Test initialization with webhook URL."""
        config = {
            "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
            "default_channel": "#general",
            "timeout": 30,
        }
        slack_plugin.initialize(config)

        assert slack_plugin._initialized is True
        assert slack_plugin._webhook_url == config["webhook_url"]
        assert slack_plugin._default_channel == config["default_channel"]
        assert slack_plugin._timeout == config["timeout"]

    def test_initialize_with_bot_token(self, slack_plugin):
        """Test initialization with bot token."""
        config = {
            "bot_token": "xoxb-test-token",
            "default_channel": "#general",
            "timeout": 45,
        }
        slack_plugin.initialize(config)

        assert slack_plugin._initialized is True
        assert slack_plugin._bot_token == config["bot_token"]
        assert slack_plugin._timeout == config["timeout"]

    def test_initialize_with_both_credentials(self, slack_plugin):
        """Test initialization with both webhook and bot token."""
        config = {
            "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
            "bot_token": "xoxb-test-token",
            "default_channel": "#general",
        }
        slack_plugin.initialize(config)

        assert slack_plugin._initialized is True
        assert slack_plugin._webhook_url == config["webhook_url"]
        assert slack_plugin._bot_token == config["bot_token"]

    def test_initialize_without_credentials_fails(self, slack_plugin):
        """Test initialization fails without credentials."""
        config = {"default_channel": "#general"}

        with pytest.raises(PluginInitializationError, match="Either 'webhook_url' or 'bot_token' must be provided"):
            slack_plugin.initialize(config)

    def test_initialize_with_invalid_timeout_fails(self, slack_plugin):
        """Test initialization fails with invalid timeout."""
        config = {
            "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
            "timeout": 500,  # Too high
        }

        with pytest.raises(PluginInitializationError, match="Timeout must be between 1 and 300 seconds"):
            slack_plugin.initialize(config)

    def test_initialize_with_minimal_config(self, slack_plugin):
        """Test initialization with minimal configuration."""
        config = {"webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST"}
        slack_plugin.initialize(config)

        assert slack_plugin._initialized is True
        assert slack_plugin._timeout == 30  # Default value


class TestSlackPluginSendMessage:
    """Test SlackPlugin send_message functionality."""

    def test_send_message_success(self, webhook_only_plugin, mock_requests):
        """Test successful message sending."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_requests.post.return_value = mock_response

        result = webhook_only_plugin.execute("send_message", {
            "text": "Test message",
            "channel": "#test",
            "urgency": "normal",
        })

        assert result["ok"] is True
        assert result["status"] == "sent"
        assert result["status_code"] == 200

        # Verify the request
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "https://hooks.slack.com" in call_args[0][0]
        assert call_args[1]["json"]["text"] == "Test message"
        assert call_args[1]["json"]["channel"] == "#test"

    def test_send_message_with_urgency_critical(self, webhook_only_plugin, mock_requests):
        """Test message sending with critical urgency."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        webhook_only_plugin.execute("send_message", {
            "text": "System down!",
            "urgency": "critical",
        })

        call_args = mock_requests.post.call_args
        message_text = call_args[1]["json"]["text"]
        assert ":rotating_light:" in message_text
        assert "CRITICAL" in message_text
        assert "System down!" in message_text

    def test_send_message_with_urgency_high(self, webhook_only_plugin, mock_requests):
        """Test message sending with high urgency."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        webhook_only_plugin.execute("send_message", {
            "text": "Important update",
            "urgency": "high",
        })

        call_args = mock_requests.post.call_args
        message_text = call_args[1]["json"]["text"]
        assert ":warning:" in message_text
        assert "HIGH PRIORITY" in message_text

    def test_send_message_with_default_channel(self, initialized_plugin, mock_requests):
        """Test message sending uses default channel when none specified."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        initialized_plugin.execute("send_message", {"text": "Test message"})

        call_args = mock_requests.post.call_args
        assert call_args[1]["json"]["channel"] == "#general"

    def test_send_message_without_webhook_fails(self, bot_token_only_plugin):
        """Test send_message fails without webhook URL."""
        with pytest.raises(PluginExecutionError, match="webhook_url is required"):
            bot_token_only_plugin.execute("send_message", {"text": "Test"})

    def test_send_message_request_failure(self, webhook_only_plugin, mock_requests):
        """Test send_message handles request failures."""
        mock_requests.post.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(PluginExecutionError, match="Failed to send Slack message"):
            webhook_only_plugin.execute("send_message", {"text": "Test"})

    def test_send_message_parameter_validation(self, webhook_only_plugin):
        """Test send_message parameter validation."""
        # Missing required parameter
        with pytest.raises(ValueError, match="Required parameter 'text' missing"):
            webhook_only_plugin.execute("send_message", {})

        # Invalid urgency value
        with pytest.raises(ValueError, match="Parameter 'urgency' must be one of"):
            webhook_only_plugin.execute("send_message", {
                "text": "Test",
                "urgency": "invalid",
            })


class TestSlackPluginSendFile:
    """Test SlackPlugin send_file functionality."""

    def test_send_file_success(self, bot_token_only_plugin, mock_requests, mock_file_system):
        """Test successful file upload."""
        mock_path, mock_open, mock_file = mock_file_system

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "file": {"id": "F123456", "name": "test.txt"}
        }
        mock_requests.post.return_value = mock_response

        result = bot_token_only_plugin.execute("send_file", {
            "file_path": "/tmp/test.txt",
            "channels": "#test",
            "initial_comment": "Test file upload",
            "title": "Test File",
        })

        assert result["ok"] is True
        assert result["file"]["id"] == "F123456"

        # Verify the request
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "files.upload" in call_args[0][0]
        assert call_args[1]["data"]["channels"] == "#test"
        assert call_args[1]["data"]["initial_comment"] == "Test file upload"

    def test_send_file_with_default_channel(self, bot_token_only_plugin, mock_requests, mock_file_system):
        """Test file upload uses default channel when none specified."""
        mock_path, mock_open, mock_file = mock_file_system

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "file": {"id": "F123456"}}
        mock_requests.post.return_value = mock_response

        bot_token_only_plugin.execute("send_file", {"file_path": "/tmp/test.txt"})

        call_args = mock_requests.post.call_args
        assert call_args[1]["data"]["channels"] == "#general"

    def test_send_file_nonexistent_file_fails(self, bot_token_only_plugin):
        """Test send_file fails with nonexistent file."""
        with patch("playbook_slack.plugin.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            with pytest.raises(PluginExecutionError, match="File not found"):
                bot_token_only_plugin.execute("send_file", {"file_path": "/nonexistent/file.txt"})

    def test_send_file_without_bot_token_fails(self, webhook_only_plugin):
        """Test send_file fails without bot token."""
        with pytest.raises(PluginExecutionError, match="bot_token is required"):
            webhook_only_plugin.execute("send_file", {"file_path": "/tmp/test.txt"})

    def test_send_file_api_error(self, bot_token_only_plugin, mock_requests, mock_file_system):
        """Test send_file handles API errors."""
        mock_path, mock_open, mock_file = mock_file_system

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "file_not_found"}
        mock_requests.post.return_value = mock_response

        with pytest.raises(PluginExecutionError, match="Slack API error: file_not_found"):
            bot_token_only_plugin.execute("send_file", {"file_path": "/tmp/test.txt"})


class TestSlackPluginCreateChannel:
    """Test SlackPlugin create_channel functionality."""

    def test_create_channel_success(self, bot_token_only_plugin, mock_requests):
        """Test successful channel creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"id": "C123456", "name": "test-channel"}
        }
        mock_requests.post.return_value = mock_response

        result = bot_token_only_plugin.execute("create_channel", {
            "name": "test-channel",
            "is_private": False,
            "purpose": "Test channel",
            "topic": "Testing",
        })

        assert result["ok"] is True
        assert result["channel"]["name"] == "test-channel"

        # Should make 3 requests: create, setPurpose, setTopic
        assert mock_requests.post.call_count == 3

    def test_create_channel_private(self, bot_token_only_plugin, mock_requests):
        """Test private channel creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"id": "C123456", "name": "private-channel"}
        }
        mock_requests.post.return_value = mock_response

        bot_token_only_plugin.execute("create_channel", {
            "name": "private-channel",
            "is_private": True,
        })

        call_args = mock_requests.post.call_args_list[0]
        assert call_args[1]["json"]["is_private"] is True

    def test_create_channel_name_taken_error(self, bot_token_only_plugin, mock_requests):
        """Test create_channel handles name_taken error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "name_taken"}
        mock_requests.post.return_value = mock_response

        with pytest.raises(PluginExecutionError, match="Channel 'existing-channel' already exists"):
            bot_token_only_plugin.execute("create_channel", {"name": "existing-channel"})

    def test_create_channel_invalid_name_error(self, bot_token_only_plugin, mock_requests):
        """Test create_channel handles invalid_name error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "invalid_name"}
        mock_requests.post.return_value = mock_response

        with pytest.raises(PluginExecutionError, match="Invalid channel name"):
            bot_token_only_plugin.execute("create_channel", {"name": "Invalid Name"})

    def test_create_channel_without_bot_token_fails(self, webhook_only_plugin):
        """Test create_channel fails without bot token."""
        with pytest.raises(PluginExecutionError, match="bot_token is required"):
            webhook_only_plugin.execute("create_channel", {"name": "test-channel"})

    def test_create_channel_name_validation(self, bot_token_only_plugin):
        """Test create_channel name pattern validation."""
        with pytest.raises(ValueError, match="does not match required pattern"):
            bot_token_only_plugin.execute("create_channel", {
                "name": "Invalid Channel Name!",
            })


class TestSlackPluginParameterValidation:
    """Test parameter validation and type conversion."""

    def test_parameter_type_conversion(self, webhook_only_plugin, mock_requests):
        """Test automatic parameter type conversion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        # Test boolean conversion from string
        webhook_only_plugin.execute("send_message", {
            "text": "Test message",
        })

        # Should succeed without errors
        assert mock_requests.post.called

    def test_unknown_function_error(self, initialized_plugin):
        """Test error handling for unknown functions."""
        with pytest.raises(PluginExecutionError, match="Unknown function: invalid_function"):
            initialized_plugin.execute("invalid_function", {})

    def test_uninitialized_plugin_error(self, slack_plugin):
        """Test error handling for uninitialized plugin."""
        with pytest.raises(PluginExecutionError, match="Plugin not initialized"):
            slack_plugin.execute("send_message", {"text": "Test"})


class TestSlackPluginCleanup:
    """Test SlackPlugin cleanup functionality."""

    def test_cleanup(self, initialized_plugin):
        """Test plugin cleanup."""
        # Verify initialized state
        assert initialized_plugin._initialized is True
        assert initialized_plugin._webhook_url is not None

        # Cleanup
        initialized_plugin.cleanup()

        # Verify cleaned state
        assert initialized_plugin._initialized is False
        assert initialized_plugin._webhook_url is None
        assert initialized_plugin._bot_token is None
        assert initialized_plugin._default_channel is None


class TestSlackPluginIntegration:
    """Integration tests for complete workflows."""

    def test_complete_workflow_simulation(self, initialized_plugin, mock_requests, mock_file_system):
        """Test a complete workflow simulation."""
        mock_path, mock_open, mock_file = mock_file_system

        # Mock responses for different operations
        mock_responses = [
            # send_message response
            Mock(status_code=200, text="ok"),
            # create_channel response
            Mock(status_code=200),
            # setPurpose response
            Mock(status_code=200),
            # setTopic response
            Mock(status_code=200),
            # send_file response
            Mock(status_code=200),
        ]

        # Configure JSON responses for API calls
        mock_responses[1].json.return_value = {
            "ok": True,
            "channel": {"id": "C123456", "name": "deploy-alerts"}
        }
        mock_responses[2].json.return_value = {"ok": True}
        mock_responses[3].json.return_value = {"ok": True}
        mock_responses[4].json.return_value = {
            "ok": True,
            "file": {"id": "F123456", "name": "deployment.log"}
        }

        mock_requests.post.side_effect = mock_responses

        # Simulate workflow steps
        # 1. Send initial notification
        result1 = initialized_plugin.execute("send_message", {
            "text": "Starting deployment process",
            "channel": "#deployments",
            "urgency": "normal",
        })
        assert result1["ok"] is True

        # 2. Create a channel for this deployment
        result2 = initialized_plugin.execute("create_channel", {
            "name": "deploy-alerts",
            "purpose": "Deployment alerts and logs",
            "topic": "Current deployment status",
        })
        assert result2["ok"] is True

        # 3. Upload deployment log
        result3 = initialized_plugin.execute("send_file", {
            "file_path": "/tmp/deployment.log",
            "channels": "#deploy-alerts",
            "initial_comment": "Deployment completed successfully",
            "title": "Deployment Log",
        })
        assert result3["ok"] is True

        # Verify all operations were called
        assert mock_requests.post.call_count == 5