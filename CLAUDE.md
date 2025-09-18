# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Playbook** is a workflow engine for operations that executes runbooks defined as TOML-based DAGs.
It supports manual approval steps, shell commands, and Python functions, making it ideal for
operational workflows and orchestrated runbooks. The project follows hexagonal architecture
principles.

## Development Commands

### Testing
```bash
# Run tests with coverage
make test
# or
python -m pytest --cov-report=xml --cov-report term --cov=src/playbook tests/
```

### Code Quality
```bash
# Run all linters
make lint

# Run ruff linter
make ruff

# Run mypy type checker
make mypy

# Format code
make format

# Auto-fix ruff issues
make ruff-fix
```

### Package Management
The project uses **UV** for package management with Python 3.13+.

```bash
# Install development dependencies
uv sync

# Install tool locally
make install

# Uninstall
make uninstall
```

### Building and Publishing
```bash
# Build package
make build

# Clean build artifacts
make clean
```

## Architecture

The codebase follows **Hexagonal Architecture** with clear separation:

- **Domain** (`src/playbook/domain/`): Core business models and ports
  - `models.py`: Pydantic models for Runbook, Node types (Manual/Command/Function), execution states
  - `ports.py`: Abstract interfaces for external dependencies

- **Service** (`src/playbook/service/`): Business logic layer
  - `engine.py`: Core RunbookEngine that orchestrates workflow execution
  - `statistics.py`: Workflow execution statistics

- **Infrastructure** (`src/playbook/infrastructure/`): External adapters
  - `cli.py`: Typer-based CLI application with Rich output
  - `persistence.py`: SQLite repositories for runs and node executions
  - `parser.py`: TOML runbook file parser
  - `process.py`: Shell command execution
  - `functions.py`: Python function loading and execution
  - `visualization.py`: Graphviz DOT export

## Key Concepts

### Node Types
- **Manual**: Requires human approval/interaction
- **Command**: Executes shell commands
- **Function**: Calls Python functions dynamically

### State Management
- Execution state persisted in SQLite (`~/.config/playbook/run.db`)
- Supports resuming failed workflows from specific nodes
- Tracks node execution attempts, status, and results

### Interactive Retry Functionality
- **Retry failed nodes**: When a node fails, users can choose to retry, skip, or abort
- **Attempt tracking**: Each retry gets a new attempt number with full state persistence
- **Max retries**: `--max-retries` option limits retry attempts (default: 3)
- **Critical nodes**: Cannot be skipped, only retried or abort workflow
- **Non-critical nodes**: Can be skipped to continue workflow execution
- **Progress preservation**: Retry loops maintain progress bar state correctly

### CLI Commands
- `playbook create`: Interactive runbook creation
- `playbook validate`: Validate runbook syntax and DAG structure
- `playbook run [--max-retries N]`: Execute runbook from start with optional retry limit
- `playbook resume <run_id> [--max-retries N]`: Resume failed execution with optional retry limit
- `playbook view-dag`: Generate and view DAG as PNG image (requires Graphviz)
  - Always saves PNG file in same directory as TOML file
  - `--keep-dot`: also save DOT file
  - `--no-open`: don't auto-open PNG (for scripting)
- `playbook info`: Show execution statistics
- `playbook show <workflow>`: Display run details

## Testing & Coverage

### Test Structure
- Tests located in `tests/` directory using pytest with coverage reporting
- Configuration in `pyproject.toml` under `[tool.pytest.ini_options]`

### Tested Functionality ✅
**Core Engine & Business Logic** - Well tested with comprehensive coverage:
- `src/playbook/service/engine.py` (73% coverage)
  - DAG validation and cycle detection
  - Workflow execution orchestration
  - **Retry functionality**: `retry_node_execution()` method with attempt tracking
  - Node execution with different types (Manual/Command/Function)
  - Resume workflow capabilities
  - Status management and error handling

- `src/playbook/domain/ports.py` (71% coverage)
  - Repository interfaces and abstractions
  - **New retry interface**: `get_latest_execution_attempt()` method

- `src/playbook/infrastructure/persistence.py` (52% coverage)
  - SQLite execution tracking and state persistence
  - **Retry persistence**: Latest execution attempt retrieval with proper isolation
  - Run and node execution repository implementations

### Untested Functionality ⚠️
**Infrastructure & CLI** - Not covered by current test suite:
- `src/playbook/infrastructure/cli.py` (0% coverage)
  - Interactive retry prompts and user input handling
  - CLI command implementations (run, resume, create, etc.)
  - Progress bar integration and error display

- `src/playbook/infrastructure/parser.py` (0% coverage)
  - TOML runbook file parsing
  - Configuration validation

- `src/playbook/infrastructure/process.py` (0% coverage)
  - Shell command execution
  - Process management and output capture

- Other infrastructure modules (0% coverage):
  - `visualization.py`: Graphviz DAG generation
  - `functions.py`: Python function loading
  - `statistics.py`: Execution statistics
  - `config.py`: Configuration management

### Test Resources
- `tests/resources/workflows/`: Real workflow examples for testing
  - `retry_basic.playbook.toml`: Basic retry scenarios
  - `critical_failure.playbook.toml`: Critical node failures
  - `mixed_nodes.playbook.toml`: Different node types
  - `parallel_dag.playbook.toml`: Parallel execution patterns

## Code Style

- **Ruff**: Linting and formatting (line length: 88)
- **MyPy**: Type checking with strict settings
- **Target**: Python 3.13+
- Configuration in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`

## Configuration

- Main config loaded from `src/playbook/config.py`
- Default state path: `~/.config/playbook/run.db`
- Environment setup via direnv (`.envrc`)
