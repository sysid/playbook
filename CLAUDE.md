# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Playbook** is a workflow engine for operations that executes runbooks defined as TOML-based DAGs. It supports manual approval steps, shell commands, and Python functions, making it ideal for operational workflows and orchestrated runbooks. The project follows hexagonal architecture principles.

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

### CLI Commands
- `playbook create`: Interactive runbook creation
- `playbook validate`: Validate runbook syntax and DAG structure
- `playbook run`: Execute runbook from start
- `playbook resume <run_id>`: Resume failed execution
- `playbook view-dag`: Generate and view DAG as PNG image (requires Graphviz)
  - Always saves PNG file in same directory as TOML file
  - `--keep-dot`: also save DOT file
  - `--no-open`: don't auto-open PNG (for scripting)
- `playbook info`: Show execution statistics
- `playbook show <workflow>`: Display run details

## Testing Patterns

- Tests located in `tests/` directory
- Uses pytest with coverage reporting
- Configuration in `pyproject.toml` under `[tool.pytest.ini_options]`

## Code Style

- **Ruff**: Linting and formatting (line length: 88)
- **MyPy**: Type checking with strict settings
- **Target**: Python 3.13+
- Configuration in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`

## Configuration

- Main config loaded from `src/playbook/config.py`
- Default state path: `~/.config/playbook/run.db`
- Environment setup via direnv (`.envrc`)