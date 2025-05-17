# DAG Specification

This document defines the structure of a Playbook DAG file, including supported node types, required fields, and default values.

## 🧭 Structure Overview

A runbook is a TOML file with the following layout:

```toml
[runbook]
title       = "Deploy Service"
description = "A workflow to deploy and verify a service"
version     = "1.0.0"
author      = "Jane Doe"
created_at  = "2024-12-01T12:00:00Z"

[node_id]
type = "Manual" | "Command" | "Function"
... (fields vary by type)
```

Each node section defines an operation to be executed in the workflow DAG.


## 🧩 Common Fields (All Node Types)

| Field           | Required | Default                          | Description                                      |
| --------------- | -------- | -------------------------------- | ------------------------------------------------ |
| `id`            | Yes      | (set by section name)            | Node identifier (must be unique)                 |
| `type`          | Yes      |                                  | Type of node: `Manual`, `Command`, or `Function` |
| `depends_on`    | No       | `[]`                             | List of node IDs this node depends on            |
| `name`          | No       | same as `id`                     | Human-friendly name                              |
| `description`   | No       | `null`                           | Description shown to the operator                |
| `skip`          | No       | `false`                          | Whether node can be skipped during execution     |
| `critical`      | No       | `false`                          | If true, failure aborts the run                  |
| `prompt_before` | No       | `""`                             | Message shown before execution                   |
| `prompt_after`  | No       | `"Continue with the next step?"` | Message shown after execution                    |


## 🔘 Node Types

### 1. Manual Node

```toml
[approval]
type = "Manual"
prompt_after = "Proceed with deployment?"
description = "Please confirm deployment readiness."
```

| Field          | Required | Default                          | Notes                                         |
| -------------- | -------- | -------------------------------- | --------------------------------------------- |
| `prompt_after` | No       | `"Continue with the next step?"` | Prompts user for approval after description   |
| `timeout`      | No       | `300`                            | Timeout in seconds                            |

### 2. Command Node

```toml
[build]
type = "Command"
command_name = "make build"
description = "Compile the application"
```

| Field          | Required | Default | Notes                                  |
| -------------- | -------- | ------- | -------------------------------------- |
| `command_name` | Yes      |         | Shell command to execute               |
| `interactive`  | No       | `false` | Allow interactive terminal access      |
| `timeout`      | No       | `300`   | Timeout in seconds                     |

### 3. Function Node

```toml
[notify]
type = "Function"
function_name = "playbook.functions.notify"
function_params = { message = "Deployment complete" }
description = "Notify team after deploy"
```

| Field             | Required | Default | Notes                           |
| ----------------- | -------- | ------- | ------------------------------- |
| `function_name`   | Yes      |         | Fully qualified Python function |
| `function_params` | No       | `{}`    | Passed as keyword arguments     |


## ⚙️ Node Execution Behavior

For all node types:

- If `prompt_before` is set (non-empty), the user will be asked to confirm before executing the node
- If `prompt_after` is set (non-empty), the user will be asked to confirm after executing the node 
- **To avoid being prompted after execution, set `prompt_after = ""`**
- If a node fails and is marked as `critical = true`, the workflow will abort
- If a node is marked as `skip = true`, it will be bypassed during execution

## 🧪 Example Workflows

### Minimal Example

```toml
[runbook]
title = "Minimal"
description = "Minimal example"
version = "1.0.0"
author = "Alice"
created_at = "2025-01-01T00:00:00Z"

[step1]
type = "Manual"
prompt_after = "Proceed?"
```

### Complex Example

```toml
[runbook]
title = "Deploy Workflow"
description = "Build, approve, and notify"
version = "1.0.0"
author = "DevOps"
created_at = "2025-01-01T00:00:00Z"

[build]
type = "Command"
command_name = "make build"
description = "Builds the service"

[approve]
type = "Manual"
prompt_after = "Deploy to production?"
description = "Manual approval step"
depends_on = ["build"]
critical = true

[deploy]
type = "Command"
command_name = "make deploy"
description = "Deploy the application"
depends_on = ["approve"]
prompt_after = ""  # No prompt after execution

[notify]
type = "Function"
function_name = "playbook.functions.notify"
function_params = { message = "Deployed successfully" }
depends_on = ["deploy"]
```

## ✨ Special Features

### Built-in Functions

The Playbook comes with several built-in functions:

```python
# Notify function
playbook.functions.notify(message: str) -> str

# Sleep function (wait for specified seconds)
playbook.functions.sleep(seconds: int) -> str

# Intentional exception (for testing error handling)
playbook.functions.throw() -> str
```

### Custom Functions

You can create your own Python functions and use them in function nodes. Functions must be importable by Python and take simple parameters (strings, numbers, booleans).
