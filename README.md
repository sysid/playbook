# Playbook

Playbook is a guided, step-by-step workflow runner for human-operated
procedures.

It is intended for operational work where a person must remain in control:
incident response, maintenance, releases, access reviews, and recurring checks.
A workflow combines written instructions, commands, and plugin functions while
preserving an audit trail in SQLite.

Playbook deliberately is not a general workflow orchestrator. It has no DAG,
parallel execution, scheduler, remote workers, or background automation. Use a
CI system, Ansible, Temporal, or another established orchestrator when the
workflow should run unattended. Use Runme when an executable Markdown notebook
is sufficient. Playbook earns its place when the primary requirement is a
terminal-based operator guide with explicit decisions and resumable state.

## Operator experience

Each enabled step is presented in file order:

```text
Daily checks / step 2 of 4 / Verify production health

Open the service dashboard and confirm the error rate is normal.

$ ./scripts/check-health
```

Required steps offer completion, execution, retry, or abort actions as
appropriate. Optional steps also offer skip. Failed commands remain at the
current step until the operator retries, skips an optional step, or aborts.

## Installation

Playbook requires Python 3.13 or newer.

```bash
uv tool install playbook
playbook --help
```

For development:

```bash
uv sync
make check
```

## Minimal workflow

Workflow files end in `.playbook.toml` and declare schema version 2.

```toml
schema_version = 3

[runbook]
id = "daily-checks"
title = "Daily checks"
description = "Review the production service at the start of the day."
version = "1.0.0"
author = "Operations"

[[steps]]
id = "open-dashboard"
type = "manual"
name = "Open the dashboard"
instructions = "Open the production overview and select the last 24 hours."
prompt = "Is the dashboard ready?"

[[steps]]
id = "check-health"
type = "command"
name = "Check service health"
instructions = "Run the read-only health check."
command = "./scripts/check-health"
timeout_seconds = 60
verify = "Does the result look healthy?"

[[steps]]
id = "record-notes"
type = "manual"
name = "Record observations"
instructions = "Add unusual findings to the operations log."
required = false
```

The order of `[[steps]]` is the execution order. There are no dependency
expressions.

See [the format reference](doc/FORMAT.md) and [the examples](examples/README.md)
for all fields.

## Commands

```bash
playbook create --output daily.playbook.toml
playbook validate daily.playbook.toml
playbook run daily.playbook.toml
playbook resume daily.playbook.toml
playbook show
playbook show daily-checks
playbook show daily-checks --run-id 3
```

`playbook show` without a workflow summarises every workflow in the state
database: how many runs it has, and when and how the most recent one ended.
Adding a workflow ID lists that workflow's runs; adding `--run-id` shows one
run's step-by-step history.

Use `--state-path` with `run`, `resume`, or `show` to override the default
database at `~/.config/playbook/run.db`.

State databases are tied to the current Playbook version. Playbook does not
migrate database schemas or preserve run history across incompatible releases.
Archive or delete an incompatible database and start a new run. Workflow files
are not migrated either: a file below `schema_version = 3` is rejected with a
message naming the required version.

Command and function steps allow at most three executions by default. Use
`--max-attempts` on `run` or `resume` to change that limit for the process.

## Variables and secrets

Variables may have defaults, types, choices, numeric limits, patterns, and a
`secret` flag:

```toml
[variables]
ENVIRONMENT = { required = true, choices = ["test", "production"] }
RUN_SECURITY = { type = "bool", default = true }
API_KEY = { required = true, secret = true }
```

Values can come from `--var KEY=VALUE`, a TOML/JSON/YAML variable file, or
environment variables prefixed with `PLAYBOOK_VAR_`. Command-line values have
highest priority.

Secret variables:

- are entered with hidden terminal input;
- are not stored in run metadata;
- are replaced with `[REDACTED]` in captured output and errors.

Redaction is exact-value replacement, not a secret manager. Prefer environment
variables or an external secret provider and avoid transforming or printing
secrets in commands. A secret interpolated into a `command` or an
`enabled_if_command` is exposed to the process table like any other argument.

### Go templates collide with `{{ }}`

Jinja renders the whole workflow file as text before it is parsed as TOML, so
`{{ ... }}` belongs to Playbook in *every* field. Tools with their own
`{{ ... }}` syntax — `docker --format`, `kubectl -o go-template`, `helm` — clash
with it:

```toml
# Fails: Jinja reads '.Server.Version' as its own expression
command = "docker version --format '{{.Server.Version}}'"
```

```
TemplateRenderError: Template rendering failed: unexpected '.'
```

The trap is that this depends on whether the workflow has variables at all.
Rendering is skipped entirely when `[variables]` is empty, so the line above
works until someone adds the first variable, and then every such command in the
file breaks at once.

Avoid the collision rather than escaping it: pick a flag that needs no template
(`docker version --format json`, `kubectl -o jsonpath=...` uses single braces),
or move the template into a script and call the script.

A `{% raw %}` block is not a reliable escape, because it fails in the mirror
image of the same trap: it produces the intended command while variables exist,
and leaks the literal `{% raw %}` markers into the command as soon as they do
not.

## Conditional steps

A step can be gated on a guard command. The guard runs when the step is
reached, and its exit code decides whether the step is presented:

```toml
[[steps]]
id = "rollback"
type = "command"
command = "./scripts/rollback"
enabled_if_command = "test -f /var/run/deploy.lock"
enabled_if_timeout_seconds = 30
```

Plain shell semantics apply: exit `0` runs the step, **any** non-zero exit code
disables it. A guard that cannot be executed at all — a typo, a missing script,
a timeout — also exits non-zero and therefore skips its step silently apart from
one console line. Keep guards short and verify them with `playbook validate`
and a dry run.

Guards must be side-effect free. They are predicates, and unlike every other
command in a workflow they run without asking the operator first.

`enabled_if_timeout_seconds` defaults to 30 and may only be set together with
`enabled_if_command`.

A guard is evaluated once per attempt, including on `resume` for steps that are
not yet complete. Steps already recorded as complete, skipped, or disabled are
not re-evaluated.

Comparing against a Boolean variable needs care. Rendered Booleans use Python
capitalisation, so the comparison value is `True`, not `true`:

```toml
[variables]
RUN_SECURITY = { type = "bool", default = true }

[[steps]]
id = "security-review"
type = "command"
command = "./scripts/security-review"
enabled_if_command = "test '{{ RUN_SECURITY }}' = 'True'"
```

Use `enabled = false` to keep a step in the document while disabling it
unconditionally. A disabled step never evaluates its guard, is recorded as
disabled, and does not prompt the operator.

## Resume and concurrency

Every run stores the source path and a SHA-256 hash of the workflow definition.
Resume fails closed if the file changed after the run started. It continues at
the first incomplete step and preserves completed, skipped, and disabled steps.
Non-secret variables must match the original run. Secret values must be supplied
again because Playbook never persists them.

An exhausted command or function step cannot run again with the same
`--max-attempts` value. Increase the limit explicitly or start a new run.

An operating-system file lock prevents two processes from running or resuming
the same workflow against the same state database. The current runner targets
POSIX systems, matching its command-execution implementation.

## Plugins

Function steps use plugins discovered through the `playbook.plugins` entry-point
group:

```toml
[[steps]]
id = "notify"
type = "function"
plugin = "slack"
function = "send_message"
params = { text = "Maintenance completed" }
config = { webhook_url = "{{ SLACK_WEBHOOK }}" }
verify = "Was the notification delivered?"
```

A fresh plugin instance is configured for each step and cleaned up immediately
after execution. This prevents configuration leaking between steps.

## Development

```bash
make format
make lint
make ty
make test
make build
```

The quality gate uses uv, Ruff, ty, pytest, and an 85 percent branch-coverage
threshold. The Slack plugin under `playbook-slack-plugin/` has the same checks.
