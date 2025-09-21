# Playbook Slack Plugin

A comprehensive Slack integration plugin for the [Playbook workflow engine](https://github.com/sysid/playbook). This plugin provides functions to send messages, upload files, and manage channels via Slack webhooks and API.

## Features

- **Send Messages**: Send formatted messages to Slack channels with urgency levels
- **Upload Files**: Upload files to Slack with optional comments and metadata
- **Create Channels**: Create new public or private channels with purpose and topic
- **Configuration Flexibility**: Support for both webhooks and bot tokens
- **Type Safety**: Full parameter validation and type conversion
- **Rich Formatting**: Support for urgency levels, custom usernames, and emojis

## Installation

### From PyPI (when published)

```bash
pip install playbook-slack
```

### From Source

```bash
git clone https://github.com/your-username/playbook-slack-plugin
cd playbook-slack-plugin
pip install -e .
```

### With UV (Recommended)

```bash
git clone https://github.com/your-username/playbook-slack-plugin
cd playbook-slack-plugin
uv sync
```

## Quick Start

### 1. Set up Slack Integration

#### Option A: Slack Webhook (for messages only)
1. Go to your Slack workspace settings
2. Create a new Incoming Webhook
3. Copy the webhook URL

#### Option B: Slack Bot Token (for full functionality)
1. Create a Slack app at https://api.slack.com/apps
2. Add the following OAuth scopes:
   - `chat:write`
   - `files:write`
   - `channels:manage`
   - `channels:read`
3. Install the app to your workspace
4. Copy the Bot User OAuth Token

### 2. Configure the Plugin

Create a runbook with plugin configuration:

```toml
[variables]
SLACK_WEBHOOK = { default = "${SLACK_WEBHOOK_URL}", description = "Slack webhook URL" }

# Global plugin configuration
[runbook.plugin_config.slack]
webhook_url = "{{SLACK_WEBHOOK}}"
default_channel = "#general"
timeout = 30

[runbook]
title = "Slack Notification Example"
description = "Send notifications to Slack"
version = "1.0.0"
author = "DevOps Team"
created_at = "2025-01-20T12:00:00Z"

[notify]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "Hello from Playbook!",
    channel = "#general",
    urgency = "normal"
}
description = "Send a test notification"
depends_on = []
```

### 3. Run the Workflow

```bash
export SLACK_WEBHOOK_URL="your-webhook-url-here"
playbook run your-workflow.playbook.toml
```

## Configuration

The plugin supports both global and per-node configuration:

### Global Configuration

```toml
[runbook.plugin_config.slack]
webhook_url = "${SLACK_WEBHOOK_URL}"          # For send_message
bot_token = "${SLACK_BOT_TOKEN}"              # For send_file, create_channel
default_channel = "#general"                  # Default channel for messages
timeout = 30                                  # Request timeout in seconds
```

### Per-Node Configuration

```toml
[critical_alert]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = { text = "Critical system alert!" }
plugin_config = {
    webhook_url = "${CRITICAL_ALERT_WEBHOOK}",  # Override global webhook
    default_channel = "#alerts"                 # Override default channel
}
```

### Environment Variables

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_DEFAULT_CHANNEL="#general"
```

## Functions Reference

### send_message

Send a formatted message to a Slack channel.

**Parameters:**
- `text` (string, required): The message text to send
- `channel` (string, optional): Channel to send message to (overrides default)
- `username` (string, optional): Username to display as sender
- `icon_emoji` (string, optional): Emoji to use as icon (e.g., ':robot_face:')
- `urgency` (string, optional): Message urgency level: `low`, `normal`, `high`, `critical`

**Requirements:** `webhook_url` in configuration

**Example:**
```toml
[deployment_success]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "Deployment of {{APP_NAME}} v{{VERSION}} completed successfully!",
    channel = "#deployments",
    username = "DeployBot",
    icon_emoji = ":rocket:",
    urgency = "high"
}
```

### send_file

Upload a file to Slack with optional message.

**Parameters:**
- `file_path` (string, required): Path to the file to upload
- `channels` (string, optional): Comma-separated channel names (e.g., '#general,#dev')
- `initial_comment` (string, optional): Optional message to accompany the file
- `title` (string, optional): Title for the file
- `filetype` (string, optional): File type (e.g., 'text', 'json', 'python')

**Requirements:** `bot_token` in configuration

**Example:**
```toml
[upload_logs]
type = "Function"
plugin = "slack"
function = "send_file"
function_params = {
    file_path = "/tmp/deployment.log",
    channels = "#dev-logs",
    initial_comment = "Deployment logs for {{APP_NAME}}",
    title = "Deployment Log - {{APP_NAME}} v{{VERSION}}",
    filetype = "text"
}
```

### create_channel

Create a new Slack channel.

**Parameters:**
- `name` (string, required): Channel name (lowercase, no spaces, alphanumeric + hyphens/underscores)
- `is_private` (boolean, optional): Whether to create a private channel (default: false)
- `purpose` (string, optional): Purpose/description of the channel
- `topic` (string, optional): Topic for the channel

**Requirements:** `bot_token` in configuration

**Example:**
```toml
[create_project_channel]
type = "Function"
plugin = "slack"
function = "create_channel"
function_params = {
    name = "project-{{PROJECT_NAME|lower}}",
    is_private = false,
    purpose = "Discussion and updates for {{PROJECT_NAME}}",
    topic = "Current sprint: {{SPRINT_NUMBER}}"
}
```

## Advanced Usage

### Multi-Step Workflow

```toml
[variables]
PROJECT_NAME = { required = true, description = "Project name" }
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }

[runbook]
title = "Complete Deployment Workflow"
description = "Deploy application with Slack notifications"
version = "1.0.0"
author = "DevOps Team"
created_at = "2025-01-20T12:00:00Z"

# Step 1: Notify deployment start
[notify_start]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "🚀 Starting deployment of {{PROJECT_NAME}} to {{ENVIRONMENT}}",
    channel = "#deployments",
    urgency = "normal"
}
depends_on = []

# Step 2: Create project channel if needed
[create_channel]
type = "Function"
plugin = "slack"
function = "create_channel"
function_params = {
    name = "{{PROJECT_NAME|lower}}-{{ENVIRONMENT}}",
    purpose = "Deployment logs for {{PROJECT_NAME}} {{ENVIRONMENT}}",
    topic = "Current deployment status"
}
depends_on = ["notify_start"]

# Step 3: Run deployment (example command)
[deploy]
type = "Command"
command_name = "kubectl apply -f deployment.yaml"
depends_on = ["create_channel"]

# Step 4: Upload deployment logs
[upload_logs]
type = "Function"
plugin = "slack"
function = "send_file"
function_params = {
    file_path = "/tmp/deployment.log",
    channels = "#{{PROJECT_NAME|lower}}-{{ENVIRONMENT}}",
    initial_comment = "Deployment completed for {{PROJECT_NAME}} v{{VERSION}}",
    title = "Deployment Log"
}
depends_on = ["deploy"]

# Step 5: Send success notification
[notify_success]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "✅ {{PROJECT_NAME}} v{{VERSION}} successfully deployed to {{ENVIRONMENT}}!",
    channel = "#deployments",
    urgency = "high"
}
depends_on = ["upload_logs"]
```

### Error Handling with Urgency Levels

```toml
# Critical alert example
[critical_alert]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "🚨 CRITICAL: Database connection failed in {{ENVIRONMENT}}",
    channel = "#alerts",
    urgency = "critical"  # Adds rotating light emojis and CRITICAL prefix
}

# High priority notification
[high_priority]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "High CPU usage detected on {{SERVER_NAME}}",
    channel = "#monitoring",
    urgency = "high"  # Adds warning emoji and HIGH PRIORITY prefix
}

# Low priority information
[info_message]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = {
    text = "Daily backup completed successfully",
    channel = "#ops",
    urgency = "low"  # Adds information emoji
}
```

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/your-username/playbook-slack-plugin
cd playbook-slack-plugin
make dev
```

### Running Tests

```bash
# Run all tests
make test

# Run tests with verbose output
make test-verbose

# Run specific test
pytest tests/test_slack_plugin.py::TestSlackPluginSendMessage::test_send_message_success -v
```

### Code Quality

```bash
# Run all linters
make lint

# Format code
make format

# Fix lint issues
make ruff-fix
```

### Building and Publishing

```bash
# Build package
make build

# Publish to Test PyPI
make publish-test

# Publish to PyPI
make publish
```

## Testing with Real Slack

To test with real Slack integration:

1. Set up environment variables:
```bash
export SLACK_WEBHOOK_URL="your-webhook-url"
export SLACK_BOT_TOKEN="your-bot-token"
```

2. Run example workflows:
```bash
make example-basic      # Basic notification
make example-advanced   # Advanced workflow with file upload and channel creation
```

## Troubleshooting

### Common Issues

1. **"webhook_url is required" error**: Make sure you have either `webhook_url` or `bot_token` configured
2. **"bot_token is required" error**: File upload and channel creation require a bot token, not just a webhook
3. **"Channel already exists" error**: The channel name is already taken, use a different name
4. **"Invalid channel name" error**: Channel names must be lowercase, alphanumeric with hyphens/underscores only

### Debugging

Enable debug logging to see detailed plugin operation:

```python
import logging
logging.getLogger('playbook_slack').setLevel(logging.DEBUG)
```

### Slack API Permissions

Make sure your Slack bot has the required permissions:
- `chat:write` - Send messages
- `files:write` - Upload files
- `channels:manage` - Create channels
- `channels:read` - Read channel information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `make test`
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

- [Playbook](https://github.com/sysid/playbook) - The main workflow engine
- [Playbook AWS Plugin](https://github.com/example/playbook-aws) - AWS integrations
- [Playbook HTTP Plugin](https://github.com/example/playbook-http) - HTTP requests

## Support

- [Issues](https://github.com/your-username/playbook-slack-plugin/issues) - Bug reports and feature requests
- [Discussions](https://github.com/your-username/playbook-slack-plugin/discussions) - General questions and discussions
- [Slack Workspace](https://join.slack.com/example) - Community chat