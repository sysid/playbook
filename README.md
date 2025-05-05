# 🛠️ Playbook

> Playbooks are guardrails for humans

**Playbook** encodes manual workflows into semi-automated processes which provide assistance, checkpoint and tools for a human operator.

It reduces pressure and heat in critical situations by guiding along a proven and tested course of action.

It supports manual approvals, shell commands, and Python functions as workflow steps — making it ideal for operations automation and orchestrated runbooks.

<p align="center">
  <img src="doc/dag.png" alt="DAG" width="200"/>
</p>


## 🚀 Features

- Runbook execution from **TOML-defined DAGs**
- Manual, command, and function nodes
- Rich CLI interface with progress display and user interaction
- Execution state stored in **SQLite** (resumable)
- DAG visualization with **Graphviz**
- Built-in statistics for workflow runs
- Extensible architecture following **Hexagonal Architecture**


## 📦 Installation

Clone this repo and set up a virtual environment:

```bash
pip install playbook
```

Run with:

```bash
./playbook --help
```


## 📝 Runbook Format (TOML)

Playbook workflows are defined as TOML files with the following structure:

### Runbook Metadata

```toml
[runbook]
title       = "Example Workflow"
description = "Demonstrates a basic DAG runbook"
version     = "0.1.0"
author      = "tw"
created_at  = "2025-05-03T12:00:00Z"
```

### Node Definition

Each node is a separate TOML table. You define:

- `type`: One of `"Manual"`, `"Command"`, `"Function"`
- `depends_on`: List of upstream node IDs (empty for roots)
- `name`: (Optional) Display name
- `description`: (Optional) Shown in CLI
- Additional fields depend on node type.

#### Manual Node

```toml
[approve]
type        = "Manual"
prompt      = "Proceed with deployment?"
description = """This step requires manual approval."""
depends_on  = ["setup"]
skippable   = false
critical    = true
```

#### Command Node

```toml
[build]
type         = "Command"
command_name = "make build"
description  = "Build artifacts"
depends_on   = ["setup"]
timeout      = 300
```

#### Function Node

```toml
[notify]
type           = "Function"
function_name  = "playbook.functions.notify"
function_params = { message = "Deployment complete" }
description    = "Notify stakeholders"
depends_on     = ["build", "tests"]
```

### Details and Specification
More info: [DAG.md](doc/DAG.md)


## 🧑‍💻 CLI Usage

### Validate a runbook

```bash
./playbook validate path/to/runbook.playbook.toml
```

### Execute a workflow

```bash
./playbook run path/to/runbook.playbook.toml
```

### Resume a failed workflow

```bash
./playbook resume path/to/runbook.playbook.toml 42
```

### Export DAG to Graphviz

```bash
./playbook export-dot path/to/runbook.playbook.toml --output dag.dot
dot -Tpng dag.dot -o dag.png
```

### Show run statistics

```bash
./playbook info
./playbook show "Example Workflow"
```


## 📂 State and Storage

- SQLite DB at `~/.config/playbook/run.db` by default
- Run and node execution state is persisted
- Allows resuming failed runs or inspecting previous ones


## 🧩 Extending

- Add new built-in functions in `playbook/functions.py`
- Add adapters for new persistence/visualization backends
- Follow domain/service/infrastructure boundaries (hexagonal)


## 📚 Example DAG Shape

Example of a DAG with branching, merging, and parallel paths:

```toml
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

[end]
type = "Command"
command_name = "echo End"
depends_on = ["e"]
```


## 🧪 Testing

To run and validate your workflow logic, use:

```bash
pytest tests/
```


## 📖 License

MIT License.  
Copyright © 2025.


## 🧠 Inspiration

This tool is inspired by Airflow, Argo Workflows, and the need for a **lightweight, local-first** DAG executor for operational workflows.
