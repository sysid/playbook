# Playbook Slack plugin

This package adds Slack function steps to Playbook 2.

Supported functions:

- `send_message` through an incoming webhook;
- `send_file` through a bot token;
- `create_channel` through a bot token.

## Development

The plugin requires Python 3.13 and uses the parent Playbook checkout as its uv
development source.

```bash
cd playbook-slack-plugin
uv sync
make check
make build
```

The published package requires `playbook>=2,<3`.

## Workflow configuration

Credentials belong in secret variables and are configured per function step:

```toml
schema_version = 2

[variables]
SLACK_WEBHOOK = { required = true, secret = true }

[runbook]
id = "slack-notification"
title = "Slack notification"

[[steps]]
id = "review"
type = "manual"
instructions = "Review the destination and message."
prompt = "Is the notification approved?"

[[steps]]
id = "notify"
type = "function"
instructions = "Send the approved message."
plugin = "slack"
function = "send_message"
params = { text = "Maintenance completed", channel = "#operations" }
config = { webhook_url = "{{ SLACK_WEBHOOK }}", timeout = 30 }
verify = "Was the message delivered?"
```

Run it with an environment variable source:

```bash
export PLAYBOOK_VAR_SLACK_WEBHOOK="https://hooks.slack.com/services/..."
playbook run notification.playbook.toml
```

Playbook redacts exact secret values from captured output, but Slack credentials
should still be kept out of workflow files, command arguments, and logs.

## Configuration fields

| Field | Used by | Meaning |
| --- | --- | --- |
| `webhook_url` | `send_message` | Incoming webhook URL |
| `bot_token` | `send_file`, `create_channel` | Slack bot token |
| `default_channel` | message and file functions | Channel used when omitted |
| `timeout` | all functions | HTTP timeout from 1 to 300 seconds |

Each function step receives a fresh plugin instance. Repeat the required
configuration in each step; configuration does not leak between steps.

## Functions

### `send_message`

Required parameter: `text`.

Optional parameters: `channel`, `username`, `icon_emoji`, and `urgency`.
`urgency` accepts `low`, `normal`, `high`, or `critical`.

Requires `webhook_url`.

### `send_file`

Required parameter: `file_path`.

Optional parameters: `channels`, `initial_comment`, `title`, and `filetype`.

Requires `bot_token` and reads the local file at execution time.

### `create_channel`

Required parameter: `name`.

Optional parameters: `is_private`, `purpose`, and `topic`.
Names must contain lowercase letters, numbers, hyphens, or underscores.

Requires `bot_token`.

See `examples/` for complete schema-v2 workflows.
