# Repository guidance

Playbook is a Python 3.13 guided workflow runner. Schema v3 is intentionally
linear: `[[steps]]` execute in file order. Do not reintroduce DAG dependencies,
parallel execution, scheduling, or implicit automation.

## Product boundary

The operator remains in control. Manual, command, and plugin-function steps are
presented one at a time. Required steps cannot be skipped. Runs are persisted in
SQLite and can resume only when the workflow definition hash is unchanged.
SQLite state uses only the current schema. There is no database migration or
runtime compatibility layer; incompatible state databases must be archived or
deleted.

The one deliberate exception is `enabled_if_command`: a step's guard command
runs without operator confirmation, because it is a predicate rather than an
action. Guards must stay side-effect free. Do not extend this into running any
other step automatically.

The plugin system is part of the supported architecture. Plugin instances are
created and configured per step, then cleaned up.

## Architecture

- `domain/`: Pydantic models, plugin contracts, and ports.
- `service/engine.py`: ordered operator interaction and execution policy.
- `infrastructure/`: TOML parsing, current SQLite state, variables,
  process execution, locking, plugins, and redaction.
- `cli/`: Typer commands and Rich terminal interaction.

## Development

Use uv; do not install packages into the global Python environment.

```bash
uv sync
make format
make lint
make ty
make test
make build
```

Tests follow red-green-refactor. Coverage must remain at or above 85 percent
with branch coverage enabled. Ruff and ty must pass for the core and Slack
plugin packages.

Do not commit, tag, publish, or mutate external systems while implementing a
change.
