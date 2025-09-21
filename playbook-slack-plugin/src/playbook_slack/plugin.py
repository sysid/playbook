"""Slack integration plugin for Playbook workflow engine."""

import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

import requests
from playbook.domain.plugins import (
    Plugin,
    PluginMetadata,
    FunctionSignature,
    ParameterDef,
    ReturnDef,
    PluginExecutionError,
    PluginInitializationError,
)

logger = logging.getLogger(__name__)


class SlackPlugin(Plugin):
    """Plugin for Slack integration functionality.

    This plugin provides functions to interact with Slack via webhooks and API:
    - Send messages to channels
    - Upload files with optional messages
    - Create new channels

    Configuration options:
    - webhook_url: Slack webhook URL for sending messages
    - bot_token: Slack bot token for API operations
    - default_channel: Default channel for messages
    - timeout: Request timeout in seconds (default: 30)
    """

    def __init__(self) -> None:
        self._initialized = False
        self._webhook_url: Optional[str] = None
        self._bot_token: Optional[str] = None
        self._default_channel: Optional[str] = None
        self._timeout: int = 30

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="slack",
            version="1.0.0",
            author="Playbook Community",
            description="Slack integration plugin for sending messages, uploading files, and managing channels",
            functions={
                "send_message": FunctionSignature(
                    name="send_message",
                    description="Send a message to a Slack channel via webhook",
                    parameters={
                        "text": ParameterDef(
                            type="str",
                            required=True,
                            description="The message text to send",
                        ),
                        "channel": ParameterDef(
                            type="str",
                            required=False,
                            description="Channel to send message to (overrides default)",
                        ),
                        "username": ParameterDef(
                            type="str",
                            required=False,
                            description="Username to display as sender",
                        ),
                        "icon_emoji": ParameterDef(
                            type="str",
                            required=False,
                            description="Emoji to use as icon (e.g., ':robot_face:')",
                        ),
                        "urgency": ParameterDef(
                            type="str",
                            required=False,
                            choices=["low", "normal", "high", "critical"],
                            default="normal",
                            description="Message urgency level",
                        ),
                    },
                    returns=ReturnDef(
                        type="dict", description="Response from Slack API"
                    ),
                    examples=[
                        {
                            "text": "Deployment completed successfully!",
                            "channel": "#deployments",
                            "urgency": "high",
                            "expected_result": {"ok": True, "status": "sent"},
                        }
                    ],
                ),
                "send_file": FunctionSignature(
                    name="send_file",
                    description="Upload a file to Slack with optional message",
                    parameters={
                        "file_path": ParameterDef(
                            type="str",
                            required=True,
                            description="Path to the file to upload",
                        ),
                        "channels": ParameterDef(
                            type="str",
                            required=False,
                            description="Comma-separated channel names (e.g., '#general,#dev')",
                        ),
                        "initial_comment": ParameterDef(
                            type="str",
                            required=False,
                            description="Optional message to accompany the file",
                        ),
                        "title": ParameterDef(
                            type="str",
                            required=False,
                            description="Title for the file",
                        ),
                        "filetype": ParameterDef(
                            type="str",
                            required=False,
                            description="File type (e.g., 'text', 'json', 'python')",
                        ),
                    },
                    returns=ReturnDef(
                        type="dict", description="Response from Slack file upload API"
                    ),
                    examples=[
                        {
                            "file_path": "/tmp/report.json",
                            "channels": "#reports",
                            "initial_comment": "Here's the latest deployment report",
                            "title": "Deployment Report",
                            "expected_result": {"ok": True, "file": {"id": "F123456"}},
                        }
                    ],
                ),
                "create_channel": FunctionSignature(
                    name="create_channel",
                    description="Create a new Slack channel",
                    parameters={
                        "name": ParameterDef(
                            type="str",
                            required=True,
                            description="Channel name (without #, lowercase, no spaces)",
                            pattern=r"^[a-z0-9_-]+$",
                        ),
                        "is_private": ParameterDef(
                            type="bool",
                            required=False,
                            default=False,
                            description="Whether to create a private channel",
                        ),
                        "purpose": ParameterDef(
                            type="str",
                            required=False,
                            description="Purpose/description of the channel",
                        ),
                        "topic": ParameterDef(
                            type="str",
                            required=False,
                            description="Topic for the channel",
                        ),
                    },
                    returns=ReturnDef(
                        type="dict", description="Response from Slack channel creation API"
                    ),
                    examples=[
                        {
                            "name": "project-alpha",
                            "is_private": False,
                            "purpose": "Discussion for Project Alpha",
                            "expected_result": {"ok": True, "channel": {"id": "C123456", "name": "project-alpha"}},
                        }
                    ],
                ),
            },
            requires=["requests"],
            config_schema={
                "webhook_url": {
                    "type": "string",
                    "description": "Slack webhook URL for sending messages",
                    "required": False,
                },
                "bot_token": {
                    "type": "string",
                    "description": "Slack bot token for API operations",
                    "required": False,
                },
                "default_channel": {
                    "type": "string",
                    "description": "Default channel for messages",
                    "required": False,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30,
                },
            },
            homepage="https://github.com/your-username/playbook-slack-plugin",
            documentation="Slack integration plugin for sending messages, uploading files, and managing channels via Slack webhook and API",
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        try:
            self._webhook_url = config.get("webhook_url")
            self._bot_token = config.get("bot_token")
            self._default_channel = config.get("default_channel")
            self._timeout = config.get("timeout", 30)

            # Validate configuration
            if not self._webhook_url and not self._bot_token:
                raise PluginInitializationError(
                    "Either 'webhook_url' or 'bot_token' must be provided in configuration"
                )

            if self._timeout < 1 or self._timeout > 300:
                raise PluginInitializationError(
                    "Timeout must be between 1 and 300 seconds"
                )

            self._initialized = True
            logger.debug("SlackPlugin initialized successfully")

        except Exception as e:
            if isinstance(e, PluginInitializationError):
                raise
            raise PluginInitializationError(f"Failed to initialize Slack plugin: {e}")

    def execute(self, function_name: str, params: Dict[str, Any]) -> Any:
        """Execute a Slack function.

        Args:
            function_name: Function to execute
            params: Function parameters

        Returns:
            Function result

        Raises:
            PluginExecutionError: If execution fails
        """
        if not self._initialized:
            raise PluginExecutionError("Plugin not initialized")

        # Validate parameters using the parent class method
        self.validate_function_params(function_name, params)

        try:
            if function_name == "send_message":
                return self._send_message(
                    text=params["text"],
                    channel=params.get("channel"),
                    username=params.get("username"),
                    icon_emoji=params.get("icon_emoji"),
                    urgency=params.get("urgency", "normal"),
                )
            elif function_name == "send_file":
                return self._send_file(
                    file_path=params["file_path"],
                    channels=params.get("channels"),
                    initial_comment=params.get("initial_comment"),
                    title=params.get("title"),
                    filetype=params.get("filetype"),
                )
            elif function_name == "create_channel":
                return self._create_channel(
                    name=params["name"],
                    is_private=params.get("is_private", False),
                    purpose=params.get("purpose"),
                    topic=params.get("topic"),
                )
            else:
                raise PluginExecutionError(f"Unknown function: {function_name}")

        except Exception as e:
            if isinstance(e, PluginExecutionError):
                raise
            raise PluginExecutionError(f"Failed to execute function {function_name}: {e}")

    def _send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        urgency: str = "normal",
    ) -> Dict[str, Any]:
        """Send a message to Slack via webhook."""
        if not self._webhook_url:
            raise PluginExecutionError("webhook_url is required for send_message function")

        # Build message payload
        payload = {"text": text}

        # Add optional parameters
        if channel or self._default_channel:
            payload["channel"] = channel or self._default_channel
        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji

        # Add urgency styling
        if urgency == "critical":
            payload["text"] = f":rotating_light: *CRITICAL* :rotating_light:\n{text}"
        elif urgency == "high":
            payload["text"] = f":warning: *HIGH PRIORITY*\n{text}"
        elif urgency == "low":
            payload["text"] = f":information_source: {text}"

        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            logger.debug(f"Message sent to Slack: {response.status_code}")
            return {
                "ok": True,
                "status": "sent",
                "status_code": response.status_code,
                "response_text": response.text,
            }

        except requests.exceptions.RequestException as e:
            raise PluginExecutionError(f"Failed to send Slack message: {e}")

    def _send_file(
        self,
        file_path: str,
        channels: Optional[str] = None,
        initial_comment: Optional[str] = None,
        title: Optional[str] = None,
        filetype: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a file to Slack via API."""
        if not self._bot_token:
            raise PluginExecutionError("bot_token is required for send_file function")

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise PluginExecutionError(f"File not found: {file_path}")

        # Build API parameters
        data = {}
        if channels:
            data["channels"] = channels
        elif self._default_channel:
            data["channels"] = self._default_channel
        if initial_comment:
            data["initial_comment"] = initial_comment
        if title:
            data["title"] = title
        if filetype:
            data["filetype"] = filetype

        try:
            with open(file_path_obj, "rb") as file_content:
                files = {"file": file_content}
                headers = {"Authorization": f"Bearer {self._bot_token}"}

                response = requests.post(
                    "https://slack.com/api/files.upload",
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=self._timeout,
                )
                response.raise_for_status()

                result = response.json()
                if not result.get("ok"):
                    raise PluginExecutionError(f"Slack API error: {result.get('error', 'Unknown error')}")

                logger.debug(f"File uploaded to Slack: {result.get('file', {}).get('id')}")
                return result

        except (OSError, IOError) as e:
            raise PluginExecutionError(f"Failed to read file {file_path}: {e}")
        except requests.exceptions.RequestException as e:
            raise PluginExecutionError(f"Failed to upload file to Slack: {e}")
        except json.JSONDecodeError as e:
            raise PluginExecutionError(f"Invalid JSON response from Slack API: {e}")

    def _create_channel(
        self,
        name: str,
        is_private: bool = False,
        purpose: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new Slack channel via API."""
        if not self._bot_token:
            raise PluginExecutionError("bot_token is required for create_channel function")

        # Choose the appropriate API endpoint
        endpoint = "conversations.create"

        # Build API parameters
        data = {
            "name": name,
            "is_private": is_private,
        }

        try:
            headers = {
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"https://slack.com/api/{endpoint}",
                json=data,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                if error == "name_taken":
                    raise PluginExecutionError(f"Channel '{name}' already exists")
                elif error == "invalid_name":
                    raise PluginExecutionError(f"Invalid channel name '{name}'. Use lowercase letters, numbers, hyphens, and underscores only")
                else:
                    raise PluginExecutionError(f"Slack API error: {error}")

            channel_id = result["channel"]["id"]

            # Set purpose and topic if provided
            if purpose:
                self._set_channel_purpose(channel_id, purpose)
            if topic:
                self._set_channel_topic(channel_id, topic)

            logger.debug(f"Channel created: {name} (ID: {channel_id})")
            return result

        except requests.exceptions.RequestException as e:
            raise PluginExecutionError(f"Failed to create Slack channel: {e}")
        except json.JSONDecodeError as e:
            raise PluginExecutionError(f"Invalid JSON response from Slack API: {e}")

    def _set_channel_purpose(self, channel_id: str, purpose: str) -> None:
        """Set the purpose of a channel."""
        try:
            headers = {
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                "https://slack.com/api/conversations.setPurpose",
                json={"channel": channel_id, "purpose": purpose},
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                logger.warning(f"Failed to set channel purpose: {result.get('error')}")

        except Exception as e:
            logger.warning(f"Failed to set channel purpose: {e}")

    def _set_channel_topic(self, channel_id: str, topic: str) -> None:
        """Set the topic of a channel."""
        try:
            headers = {
                "Authorization": f"Bearer {self._bot_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                "https://slack.com/api/conversations.setTopic",
                json={"channel": channel_id, "topic": topic},
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                logger.warning(f"Failed to set channel topic: {result.get('error')}")

        except Exception as e:
            logger.warning(f"Failed to set channel topic: {e}")

    def cleanup(self) -> None:
        """Clean up plugin resources."""
        self._webhook_url = None
        self._bot_token = None
        self._default_channel = None
        self._initialized = False
        logger.debug("SlackPlugin cleaned up")