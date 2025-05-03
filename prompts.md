
### 1  High‑Level Blueprint

| Phase | Goal | Key Deliverables |
|-------|------|------------------|
| **0. Bootstrap** | Repo, CI, skeleton CLI | Git repo, `poetry`/`pip-tools`, `typer` entry‑point |
| **1. Domain** | Pure business objects & validation | Pydantic models for runbook, nodes |
| **2. Infrastructure: Parsing** | Load/validate *.playbook.toml* | TOML parser, schema errors surfaced |
| **3. Infrastructure: Persistence** | SQLite repo w/ migrations | `RunRepository`, `ExecutionRepository` |
| **4. Service: Engine** | DAG planner + executor | Topological sort, node runners |
| **5. CLI Commands** | `create`, `run`, `resume`, … | Typer subcommands & options |
| **6. Graphviz Export** | Styled *.dot* writer | Shapes/colors per spec |
| **7. Polish & Ops** | Config file, logging, tests | `~/.config/playbook/config.toml`, `pytest`, GitHub CI |

---

### 2  Iterative Chunks

1. **Repo & Tooling**  
2. **Runbook Metadata Model**  
3. **Node Model & Validation**  
4. **TOML Loader & Basic `validate`**  
5. **SQLite Repositories (runs & executions)**  
6. **Simple Engine (linear, no persistence)**  
7. **Topological Execution & `depends_on` checks**  
8. **Manual Node Runner w/ prompts**  
9. **Command Runner (live stream)**  
10. **Function Runner (dynamic import)**  
11. **Retry/Skip/Abort Loop**  
12. **State Checkpoint & `resume`**  
13. **Global Config & Timeout**  
14. **Graphviz Exporter**  
15. **CLI `create` Scaffold**  
16. **`info` & `show` Commands**  
17. **End‑to‑End Tests & Docs**

---

### 3  Right‑Sizing Pass

| Chunk | Sub‑steps (each ≤ ~1 hr coding) |
|-------|---------------------------------|
| **1** | init git; add **pyproject**; add `main.py` w/ Typer stub; set up CI |
| **2** | add `RunbookMeta` pydantic; unit‑test defaults |
| **3** | add `BaseNode` + `ManualNode`; enum for type; validate defaults |
| **4** | implement `Runbook.from_toml(path)`; raise cycle detection TODO |
| **5** | create `sqlite3` file; write migration `create tables`; write `RunRepository.add_run` |
| **6** | naive engine: iterate nodes order as listed; invoke `ManualNode` only |
| **7** | topological sort util; replace naive order; test cycle error |
| **8** | implement `ManualRunner`; prompt ok/nok + note |
| **9** | add `CommandRunner` (subprocess); live stream via `rich`; capture to DB |
| **10** | add `FunctionRunner`; load via `importlib`; handle `"${ask}"` |
| **11** | central retry/skip/abort loop; integrate `repeatable`, `skippable`, `critical` |
| **12** | persist after each node; implement `resume --node` |
| **13** | parse `config.toml`; inject default timeout & `state_path` |
| **14** | write `.dot` exporter; map shapes/colors; unit‑test |
| **15** | `create` command: prompt/flags; write sample runbook |
| **16** | `info` stats query; `show` nicely formatted log (plain / JSON) |
| **17** | integration tests covering happy path, failure, skip; docs README |

All steps now small, linear, and integrate previous work—no orphans.

---

### 4  Code‑Generation Prompts

Below are LLM prompts (one per sub‑step). Each is standalone, references prior code, and ends by **wiring new code into the package**.

---

#### Prompt 1‑1 (init repo & CLI)

```text
You have an empty Git repo.  
Create the minimal project scaffold:

* `pyproject.toml` using Poetry, Python 3.12. Name: `playbook`, version `0.0.1`.
* Package `playbook/` with empty `__init__.py`.
* `playbook/main.py` defining a Typer app with a single `--version` option.

Include `README.md` with setup instructions.  
Make sure `python -m playbook.main --version` prints the version string.  
Return full files ready to commit.
```

---

#### Prompt 1‑2 (set up CI)

```text
The repo from Prompt 1‑1 now exists.  
Add GitHub Actions CI:

* Workflow `python.yml` triggers on push/pull‑request.
* Matrix: Python 3.12 only.
* Steps: checkout, setup‑python, install Poetry, install deps, run `pytest` (no tests yet).

Return only the new workflow file content.
```

---

#### Prompt 2‑1 (RunbookMeta model)

```text
Extend the existing package.

* Add `playbook/domain/models.py` containing a Pydantic `RunbookMeta` model with fields:
  `title` (str), `description` (str), `version` (str), `author` (str),
  `created_at` (datetime). All are required.  
* Provide `from_defaults()` classmethod that fills `version="0.1.0"` and
  `created_at=datetime.utcnow()` while requiring the rest.

Write unit tests in `tests/test_runbook_meta.py` covering validation and defaults.  
Update `__init__.py` to export `RunbookMeta`.
```

---

#### Prompt 3‑1 (Node base & ManualNode)

```text
Add node classes.

* In `playbook/domain/node.py` define:
  * Enum `NodeType` with `MANUAL`, `FUNCTION`, `COMMAND`.
  * `BaseNode` Pydantic with common fields (id, type, depends_on, repeatable,
    skippable, critical, name, timeout).
  * `ManualNode` inheriting `BaseNode` with extra `prompt: str`.

Add factory `parse_node(table_key: str, data: dict) -> BaseNode`
that instantiates correct subclass by `type`.

Write unit tests parsing a sample Manual node TOML dict.
```

---

#### Prompt 4‑1 (TOML loader & basic validate)

```text
Implement runbook loader.

* Add dependency `tomli`.
* In `playbook/infrastructure/parser.py` implement `RunbookLoader.load(path: Path)
  -> tuple[RunbookMeta, dict[str, BaseNode]]`.
  * Parse TOML.
  * Build `RunbookMeta` from `[runbook]`.
  * Iterate remaining tables, parse nodes.
  * Detect duplicate ids, raise ValueError.

Wire `playbook/main.py validate` command:
  `playbook validate file.playbook.toml` prints "Valid ✔" or errors.

Add unit test with a minimal TOML.
```

---

#### Prompt 5‑1 (SQLite migrations & RunRepository)

```text
Add persistence.

* New module `playbook/infrastructure/sqlite_repo.py`.
* On init, create tables `runs` and `executions` exactly per spec.
* Implement class `RunRepository` with methods:
  `create_run(workflow_name) -> int`  (returns new run_id),
  `complete_run(...)`,
  `add_execution(...)`.

Write tests using in‑memory SQLite (`":memory:"`) verifying schema and
auto‑increment per workflow.
```

---

#### Prompt 6‑1 (Simple engine loop)

```text
Create first engine iteration.

* `playbook/service/engine.py` with class `Engine`.
* Accept meta, nodes dict, repositories, and Clock port.
* Execute nodes in file order (ignore depends_on).
* Only ManualNode supported: prompt operator in console using `input()`.
* Record executions and run summary.

Wire a new CLI command `run`.  
Unit‑test engine happy path with mocked `input` returning "ok".
```

---

*(Continue with prompts 7‑1 … 17‑1 following the sub‑step table. Each prompt specifies the file(s) to change, required tests, and integration into CLI or services. Due to space, subsequent prompt texts follow the same pattern and can be generated as needed.)*

---

These prompts provide a **safe, incremental path** from skeleton to full‑featured prototype, aligning with clean architecture and facilitating later porting to Rust.
