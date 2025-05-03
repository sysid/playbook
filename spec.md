
### **Playbook Engine – Prototype Specification**

---

## 1  Runbook file (`*.playbook.toml`)

```toml
[runbook]                # ‑‑ mandatory metadata
title       = "Deploy"
description = "Blue/green deployment"
version     = "0.1.0"
author      = "Ops Team"
created_at  = "2025‑05‑03T12:08:00Z"

# Each node is a top‑level table; table key = node‑id
[build]
type        = "Command"
command_name = "docker build -t myapp:latest ."
depends_on  = []
repeatable  = false     # default; may be omitted
skippable   = false
critical    = true      # cannot be skipped
name        = "Build image"   # optional alt title
timeout     = 600       # seconds (falls back to config)

[approve]
type       = "Manual"
prompt     = "Deploy to production?"
depends_on = ["build"]
skippable  = false
critical   = true
```

### 1.1 Common node fields (defaults)

| Field        | Type    | Default | Meaning |
|--------------|---------|---------|---------|
| `type`       | string  | —       | `Manual` \| `Function` \| `Command` |
| `depends_on` | string[]| `[]`    | Prerequisite node ids |
| `repeatable` | bool    | `false` | On resume, prompt to rerun |
| `skippable`  | bool    | `false` | Operator may skip |
| `critical`   | bool    | `false` | Must end `ok`; skip not allowed |
| `name`       | string  | table key | Human label |
| `timeout`    | int     | config default (`300`) | Seconds; node‑level override |

### 1.2 Type‑specific fields

| Node type | Required fields | Success rule |
|-----------|-----------------|--------------|
| **Manual** | `prompt` (string) | Operator chooses `ok` / `nok`; optional free‑text note recorded as `result_text`. |
| **Function** | `function_name` (fully‑qualified import path), `function_params` (dict). Values equal to `"${ask}"` trigger runtime prompt (plain string). Any uncaught exception ⇒ `nok`. |
| **Command** | `command_name` (full shell string, env vars like `$HOME` / `~` interpolated). Non‑zero exit‑code ⇒ `nok`. `stdout`/`stderr` streamed live and captured. |

---

## 2  Operator flow & rules

* **Execution order:** DAG topological, one node at a time.
* **`nok` handling:** engine prompts  
  * `r` retry (new `attempt`)  
  * `s` skip (only if `skippable = true`)  
  * `a` abort (stop run, mark run `nok`)
* **Skip semantics:** skipped node counts as satisfied for dependents.
* **Critical failure:** any critical node `nok` ⇒ entire run `nok`.
* **Dependent on failed node:** downstream nodes never run.

---

## 3  CLI (Typer)

```
playbook [global flags] <subcommand> …

Global flags        -v  DEBUG log level
                    --version
                    --state-path <file>   # overrides config

Subcommands
  create      --title --author --description --output <file>
  run         <file>
  resume      <file> [--node <node-id>]
  validate    <file> [--strict]
  export-dot  <file> [--output <dot>]
  info        [--json]        # DB stats/schema
  show        <workflow> [--run-id <n>]
```

---

## 4  Configuration (`~/.config/playbook/config.toml`)

```toml
default_timeout_seconds = 300
state_path              = "~/.config/playbook/run.db"
```

*CLI flags > config file > hard‑coded defaults.*

---

## 5  Persistence (SQLite, via `state_path`)

### 5.1 Run table (`runs`)

| Column | Type | Notes |
|--------|------|-------|
| workflow_name | TEXT | part of PK |
| run_id        | INTEGER | autoincrement per workflow (PK) |
| start_time    | TEXT (UTC ISO‑8601) |
| end_time      | TEXT |
| status        | TEXT `ok`/`nok` |
| nodes_ok / nodes_nok / nodes_skipped | INTEGER |
| trigger       | TEXT (`run` \| `resume`) |

### 5.2 Node‑execution table (`executions`)

| Column | Type | Notes |
|--------|------|-------|
| workflow_name, run_id | (FK) |
| node_id   | TEXT |
| attempt   | INTEGER |
| start_time / end_time | TEXT |
| status    | TEXT `ok`/`nok`/`skipped` |
| operator_decision | TEXT |
| result_text | TEXT |
| exit_code  | INTEGER |
| exception  | TEXT |
| stdout / stderr | TEXT |
| duration_ms | INTEGER |

---

## 6  Graphviz export (`export-dot`)

* **Shapes / fills**  
  * Manual – ellipse, light‑blue fill  
  * Function – box, light‑green fill  
  * Command – hexagon, light‑yellow fill  
* **Critical nodes**: 2 px red border  
* File placed next to runbook unless `--output` supplied.

---

## 7  Prototype implementation guidelines

* **Language:** Python 3.12  
* **Architecture:** Clean/hexagonal  
  * Layers: **domain** (Pydantic models), **service** (engine orchestrator), **infrastructure** (SQLite, CLI, Graphviz, OS)  
  * Dependencies point inwards; use interfaces/ports.  
* **Key libs:** `typer`, `rich`, `pydantic`, `importlib`, `sqlite3`, `graphviz`.  
* **Coding style:** Rust‑like separation, repository pattern for persistence, dependency injection for ports (e.g., `Clock`, `ProcessRunner`).  
* **Testing:** unit tests per layer; temp SQLite dbs.

The specification above captures all functional, data‑model, CLI, and runtime decisions agreed during our dialog and is ready for development.
