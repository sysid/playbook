# 🧭 DAG Specification

This document describes the **TOML-based DAG format** used by the Playbook workflow engine. A runbook is a directed acyclic graph (DAG) of *nodes*, each representing a unit of work. Edges between nodes define **dependencies**.

## 📘 Structure Overview

A valid `.playbook.toml` file contains:

1. A required `[runbook]` metadata block.
2. One or more node definitions (`[<node_id>]`) with a `type`.

## 🧱 Node Types

| Type     | Description                            | Supported Fields |
|----------|----------------------------------------|------------------|
| `Manual` | Waits for operator input               | `prompt`, `confirm`, `skippable`, `critical` |
| `Command`| Executes a shell command               | `command_name`, `timeout` |
| `Function`| Calls a Python function by path       | `function_name`, `function_params` |


## 🧾 Required: Runbook Metadata

```toml
[runbook]
title       = "My Workflow"
description = "Human-readable summary"
version     = "0.1.0"
author      = "Jane Doe"
created_at  = "2025-05-03T12:00:00Z"
```

| Field        | Required | Type    | Description |
|--------------|----------|---------|-------------|
| `title`      | ✅       | string  | Unique name of workflow |
| `description`| ✅       | string  | Purpose of the workflow |
| `version`    | ✅       | string  | Semantic version |
| `author`     | ✅       | string  | Author name |
| `created_at` | ✅       | RFC3339 | Timestamp of creation |


## 🧩 Node Fields

Each node is a table named `[<node_id>]` and includes these fields:

| Field          | Required | Default     | Applies To      | Description |
|----------------|----------|-------------|-----------------|-------------|
| `type`         | ✅       | —           | All             | Node type: `Manual`, `Command`, `Function` |
| `depends_on`   | ✅       | `[]`        | All             | List of other node IDs |
| `name`         | ❌       | `node_id`   | All             | Display name |
| `description`  | ❌       | `""`        | All             | Human-readable explanation |
| `skippable`    | ❌       | `false`     | All             | Can be skipped if failed |
| `critical`     | ❌       | `false`     | All             | Causes workflow to abort if failed |
| `timeout`      | ❌       | `300`       | `Command`, `Function` | Timeout in seconds |
| `prompt`       | ✅       | `Confirm?` | All        | Prompt message for user, `""` to skip prompting |
| `confirm`      | ❌       | `true`      | `Manual`, `Function`, `Command` | Ask for confirmation |
| `command_name` | ✅       | —           | `Command`       | Shell command to run |
| `function_name`| ✅       | —           | `Function`      | Fully-qualified Python function path |
| `function_params` | ❌    | `{}`        | `Function`      | Arguments passed to the function |


## ✅ Minimal Example

```toml
[runbook]
title       = "Simple Demo"
description = "Hello World example"
version     = "0.1.0"
author      = "tw"
created_at  = "2025-05-03T12:00:00Z"

[start]
type         = "Command"
command_name = "echo Hello"
depends_on   = []
```


## 🧠 Complex Example

```toml
[runbook]
title       = "Complex DAG"
description = "Demonstrates branching and joins"
version     = "0.2.0"
author      = "tw"
created_at  = "2025-05-03T13:00:00Z"

[start]
type = "Command"
command_name = "echo Start"
depends_on = []

[a]
type = "Command"
command_name = "echo A"
depends_on = ["start"]

[b]
type = "Command"
command_name = "echo B"
depends_on = ["start"]

[e]
type = "Command"
command_name = "echo E"
depends_on = ["a", "b"]

[c]
type = "Function"
function_name = "playbook.functions.notify"
function_params = { message = "Finished A" }
depends_on = ["a"]

[d]
type = "Manual"
prompt = "Did B succeed?"
depends_on = ["b"]

[f]
type = "Command"
command_name = "echo F"
depends_on = ["c", "d"]

[g]
type = "Command"
command_name = "echo G"
depends_on = ["e"]

[end]
type = "Command"
command_name = "echo Done"
depends_on = ["f", "g"]
```

## 🧪 Validating Runbooks

```bash
./playbook validate path/to/runbook.playbook.toml
```

- Checks for missing fields
- Validates dependency references
- Detects cyclic graphs


## 📤 Exporting DAGs

Render the DAG using Graphviz:

```bash
./playbook export-dot workflow.playbook.toml --output dag.dot
dot -Tpng dag.dot -o dag.png
```


## 🧩 Extending Node Types

To support new node types (e.g. HTTP, SSH), implement a new subclass of `BaseNode` and add execution logic to the `RunbookEngine`.


## 🧠 Tips

- Prefer meaningful node IDs like `setup_db`, `notify_ops`
- Use `description` to make the CLI output user-friendly
- Use `critical=true` on key nodes that must not be skipped
