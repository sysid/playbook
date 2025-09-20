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
  - `exceptions.py`: Custom exception hierarchy with context and actionable suggestions

- **Service** (`src/playbook/service/`): Business logic layer
  - `engine.py`: Core RunbookEngine that orchestrates workflow execution
  - `statistics.py`: Workflow execution statistics

- **Infrastructure** (`src/playbook/infrastructure/`): External adapters
  - `persistence.py`: SQLite repositories for runs and node executions
  - `parser.py`: TOML runbook file parser
  - `process.py`: Shell command execution
  - `functions.py`: Python function loading and execution
  - `visualization.py`: Graphviz DOT export

- **CLI** (`src/playbook/cli/`): Modular command-line interface
  - `main.py`: Typer application setup and command registration
  - `commands/`: Individual command implementations (create, run, validate, etc.)
  - `error_handler.py`: Rich-formatted error display with context and suggestions
  - `interaction/handlers.py`: User interaction and progress display
  - `common.py`: Shared utilities and error handling functions

- **Configuration** (`src/playbook/config/`): Environment-based configuration system
  - `manager.py`: Configuration loading, validation, and template generation
  - Support for development/testing/production environments
  - TOML-based configuration with environment variable overrides

## Key Concepts

### Node Types
- **Manual**: Requires human approval/interaction
- **Command**: Executes shell commands
- **Function**: Calls Python functions dynamically

### State Management
- Execution state persisted in SQLite (configurable path, default: `~/.config/playbook/run.db`)
- Supports resuming failed workflows from specific nodes
- Tracks node execution attempts, status, and results
- Database backup and rotation configurable

### Interactive Retry Functionality
- **Retry failed nodes**: When a node fails, users can choose to retry, skip, or abort
- **Attempt tracking**: Each retry gets a new attempt number with full state persistence
- **Max retries**: `--max-retries` option limits retry attempts (default: 3)
- **Critical nodes**: Cannot be skipped, only retried or abort workflow
- **Non-critical nodes**: Can be skipped to continue workflow execution
- **Progress preservation**: Retry loops maintain progress bar state correctly

### CLI Commands
- `playbook create`: Interactive runbook creation with node templates
- `playbook validate`: Validate runbook syntax and DAG structure with rich error reporting
- `playbook run [--max-retries N]`: Execute runbook from start with optional retry limit
- `playbook resume <run_id> [--max-retries N]`: Resume failed execution with optional retry limit
- `playbook view-dag`: Generate and view DAG as PNG image (requires Graphviz)
  - Always saves PNG file in same directory as TOML file
  - `--keep-dot`: also save DOT file
  - `--no-open`: don't auto-open PNG (for scripting)
- `playbook info`: Show execution statistics and database information
- `playbook show <workflow>`: Display run details with status and timing
- `playbook config`: Configuration management
  - `--show`: Display current configuration across all sections
  - `--init <env>`: Initialize configuration for environment (dev/test/prod)
  - `--validate`: Validate current configuration with warnings
  - `--template <path>`: Create configuration template file

### Error Handling & User Experience
- **Rich error formatting**: Color-coded panels with clear titles and suggestions
- **Contextual information**: Detailed context for debugging complex issues
- **Actionable suggestions**: Specific steps to resolve common problems
- **Graceful degradation**: Non-critical failures don't stop workflow execution
- **Verbose mode**: Full stack traces available with `-v/--verbose` flag

## Testing & Coverage

### Test Structure
- Tests located in `tests/` directory using pytest with coverage reporting
- Configuration in `pyproject.toml` under `[tool.pytest.ini_options]`
- **Current Coverage**: 48.25% (improved from 29% baseline)
- **Total Tests**: 76 tests, all passing

### Well-Tested Components ✅
**Core Engine & Business Logic** - Comprehensive coverage:
- `src/playbook/service/engine.py` (70% coverage)
  - DAG validation and cycle detection
  - Workflow execution orchestration
  - **Retry functionality**: Complete retry loop with attempt tracking
  - Node execution with all types (Manual/Command/Function)
  - Resume workflow capabilities
  - Status management and error handling

- `src/playbook/domain/ports.py` (71% coverage)
  - Repository interfaces and abstractions
  - Retry interface with latest execution attempt retrieval

- **CLI Commands** (82-86% coverage):
  - `src/playbook/cli/commands/create.py`: Interactive runbook creation
  - `src/playbook/cli/commands/validate.py`: Validation with error handling
  - Comprehensive CLI testing using Typer's CliRunner

- **Infrastructure Components** (52-92% coverage):
  - `src/playbook/infrastructure/persistence.py`: SQLite execution tracking
  - `src/playbook/infrastructure/parser.py`: TOML parsing and validation
  - `src/playbook/infrastructure/process.py`: Command execution
  - `src/playbook/infrastructure/functions.py`: Python function loading

### Partially Tested Components ⚠️
**CLI & Configuration** - Moderate coverage:
- `src/playbook/cli/error_handler.py` (43% coverage): Rich error formatting
- `src/playbook/config/manager.py` (52% coverage): Configuration management
- Various CLI commands (12-14% coverage): Need integration testing

### Untested Components 📝
**Statistics & Visualization** - Require dedicated test suites:
- `src/playbook/infrastructure/statistics.py` (9% coverage)
- `src/playbook/infrastructure/visualization.py` (15% coverage)
- Legacy `src/playbook/functions.py` and `src/playbook/config.py` (0% coverage)

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

## Configuration System

### Environment-Based Configuration
The project uses a flexible TOML-based configuration system with environment support:

- **Configuration Discovery**: Local → User (`~/.config/playbook/`) → System (`/etc/playbook/`)
- **Environment Selection**: Use `PLAYBOOK_ENV` environment variable (development/testing/production)
- **File Precedence**: `playbook.toml` (local) → `{env}.toml` → `config.toml`

### Configuration Sections
```toml
[database]
path = "~/.config/playbook/run.db"  # SQLite database location
timeout = 30                        # Connection timeout (seconds)
backup_enabled = true              # Automatic backup creation
backup_count = 5                   # Number of backups to keep

[execution]
default_timeout = 300              # Default command timeout
max_retries = 3                    # Default retry attempts
interactive_timeout = 1800         # Interactive command timeout
parallel_execution = false         # Enable parallel node execution

[logging]
level = "INFO"                     # DEBUG, INFO, WARNING, ERROR, CRITICAL
file_path = ""                     # Log file path (empty = console only)
max_size_mb = 10                   # Log rotation size
backup_count = 3                   # Rotated log files to keep

[ui]
progress_style = "bar"             # Progress display style
color_theme = "auto"               # auto, light, dark, none
show_timestamps = true             # Show timestamps in output
compact_output = false             # Use compact formatting
```

### Environment Variable Overrides
- `PLAYBOOK_ENV`: Environment name (development/testing/production)
- `PLAYBOOK_CONFIG`: Direct config file path
- `PLAYBOOK_DB_PATH`: Override database path
- `PLAYBOOK_LOG_LEVEL`: Override logging level
- `PLAYBOOK_LOG_FILE`: Override log file path
- `PLAYBOOK_MAX_RETRIES`: Override default max retries
- `PLAYBOOK_DEFAULT_TIMEOUT`: Override default timeout

### Development Setup
- Environment setup via direnv (`.envrc`)
- UV for package management with Python 3.13+
