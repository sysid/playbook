# Workflow format

## Document structure

A workflow is a TOML document with four parts:

```toml
schema_version = 3

[variables]
# Optional variable definitions

[runbook]
id = "stable-machine-id"
title = "Human-readable title"

[[steps]]
# Ordered step definitions
```

`schema_version`, `[runbook]`, and `steps` are required. `steps = []` is valid
for a newly created workflow; useful workflows normally use one or more
`[[steps]]` tables.

## Runbook metadata

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable ID used for state, locks, and resume |
| `title` | yes | Operator-facing workflow name |
| `description` | no | Purpose and scope |
| `version` | no | Workflow version chosen by the author |
| `author` | no | Owning person or team |

Changing any file content changes the definition hash and prevents an existing
run from being resumed.

## Common step fields

| Field | Default | Meaning |
| --- | --- | --- |
| `id` | required | Unique letters, numbers, `_`, or `-` |
| `type` | required | `manual`, `command`, or `function` |
| `name` | step ID | Operator-facing name |
| `instructions` | none | Context and action for the operator |
| `required` | `true` | When false, skip is offered |
| `enabled` | `true` | When false, record as disabled |
| `enabled_if_command` | none | Guard command; exit 0 enables the step |
| `enabled_if_timeout_seconds` | `30` | Guard timeout; requires `enabled_if_command` |

Steps execute exactly in file order. A disabled step still occupies its
position, is recorded as disabled, and does not prompt.

## Conditional steps

`enabled_if_command` is evaluated when the step is reached, before the operator
is prompted:

```toml
[[steps]]
id = "rollback"
type = "command"
command = "./scripts/rollback"
enabled_if_command = "test -f /var/run/deploy.lock"
enabled_if_timeout_seconds = 30
```

| Guard result | Step outcome |
| --- | --- |
| exit 0 | Presented to the operator as usual |
| any non-zero exit | Recorded as disabled with decision `condition-false` |
| command not found, timeout, execution error | Non-zero, so also disabled |

The guard's exit code, stdout, and stderr are redacted and persisted with the
disabled step. One console line names the step, the guard, and the exit code;
nothing else is printed and the operator is not prompted.

Guards run without operator confirmation, so they must be side-effect free.
They are re-evaluated on resume for steps that are not yet complete.

A rendered Boolean variable uses Python capitalisation, so compare against
`True` rather than `true`:

```toml
enabled_if_command = "test '{{ RUN_SECURITY }}' = 'True'"
```

`enabled = false` disables a step unconditionally and its guard is never run.

## Manual step

```toml
[[steps]]
id = "review-change"
type = "manual"
name = "Review the change"
instructions = "Compare the proposed change with the approved ticket."
prompt = "Is the review complete?"
```

`instructions` is required. `prompt` defaults to `Done?`.

## Command step

```toml
[[steps]]
id = "health-check"
type = "command"
instructions = "Run the read-only service health check."
command = "./scripts/health-check"
interactive = false
timeout_seconds = 120
verify = "Is the reported state healthy?"
```

`command` is required. `timeout_seconds` defaults to 300 and must be positive.
Interactive commands inherit the terminal. Non-interactive commands have their
stdout and stderr captured, redacted, displayed, and persisted.

## Function step

```toml
[[steps]]
id = "notify"
type = "function"
instructions = "Notify the operations channel."
plugin = "slack"
function = "send_message"
params = { text = "Checks completed" }
config = { webhook_url = "{{ SLACK_WEBHOOK }}" }
verify = "Was the message delivered?"
```

`plugin` and `function` are required. `params` and `config` default to empty
tables. Plugin metadata defines valid function parameters.

## Variables

Literal values are shorthand for defaults:

```toml
[variables]
APPLICATION = "orders"
```

Full definitions support:

| Field | Meaning |
| --- | --- |
| `default` | Value used when no source provides one |
| `required` | Require a value or interactive input |
| `type` | `string`, `int`, `float`, `bool`, or `list` |
| `choices` | Allowed values |
| `description` | Prompt context |
| `min`, `max` | Numeric bounds |
| `pattern` | String regular expression |
| `secret` | Hide input and redact exact values |

Jinja expressions are rendered in string fields after variables are resolved.
The environment is sandboxed and undefined values fail validation.

## Operator decisions

| Step state | Required choices | Optional choices |
| --- | --- | --- |
| Manual | done, abort | done, skip, abort |
| Before command/function | run, abort | run, skip, abort |
| Failed command/function | retry, abort | retry, skip, abort |
| Verification | done, retry, abort | done, retry, abort |

Abort persists the run as aborted. Resume continues with the first step that is
not complete, skipped, or disabled. The workflow definition and all non-secret
variable values must match the original run. Secret variables must be supplied
again because they are not persisted. A command or function step that exhausted
its configured attempt limit requires a higher `--max-attempts` value before it
can be resumed.
