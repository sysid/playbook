# 🛠️ Playbook

> Playbooks are guardrails for humans

**Playbook** encodes manual workflows into semi-automated processes which provide assistance, checkpoint and tools for a human operator.

It reduces pressure and heat in critical situations by guiding along a proven and tested course of action.

It supports manual approvals, shell commands, and Python functions as workflow steps — making it ideal for operations automation and orchestrated runbooks.

<p align="center">
  <img src="doc/dag.png" alt="DAG" width="200"/>
</p>


## 🚀 Features

- **TOML-defined DAGs** with comprehensive workflow orchestration
- **Variable support** with Jinja2 templating for dynamic, environment-aware workflows
- **Simplified dependency syntax** with implicit linear dependencies and special keywords
- **Conditional dependencies** with shorthand syntax and complex branching logic
- **Plugin system** for extensible functionality with external packages
- **Interactive retry functionality** with configurable retry limits and failure handling
- **Manual, command, and function nodes** with rich descriptions and context
- **Configuration management** with environment-based settings and overrides
- **Rich CLI interface** with progress display, user interaction, and comprehensive error handling
- **Execution state persistence** in SQLite with full resumability and attempt tracking
- **DAG visualization** with Graphviz export and automatic image generation
- **Built-in statistics** and execution analytics for workflow runs
- **Extensible architecture** following Hexagonal Architecture principles


## 📦 Installation

Install Playbook from PyPI:

```bash
pip install playbook
```

Install with additional plugins:

```bash
# Install with commonly used plugins
pip install playbook playbook-slack playbook-http

# Or install plugins separately as needed
pip install playbook
pip install playbook-aws playbook-k8s
```

Run with:

```bash
playbook --help
```


## 📝 Runbook Format (TOML)

Playbook workflows are defined as TOML files with the following structure:

### Runbook Metadata

```toml
[runbook]
title       = "Example Workflow"
description = """
Comprehensive workflow demonstrating DAG execution with multiple node types.
This runbook showcases manual approvals, automated commands, and plugin integration
to provide a complete operational automation solution.
"""
version     = "0.1.0"
author      = "tw"
created_at  = "2025-05-03T12:00:00Z"
```

### Node Definition

Each node is a separate TOML table. You define:

- `type`: One of `"Manual"`, `"Command"`, `"Function"`
- `depends_on`: Dependencies (see Dependency Syntax below)
- `name`: (Optional) Display name
- `description`: (Optional) Shown in CLI
- Additional fields depend on node type.

#### Dependency Syntax

Playbook provides flexible dependency syntax to reduce verbosity for common patterns:

**Implicit Linear Dependencies (Default)**
When `depends_on` is omitted, nodes automatically depend on the previous node in declaration order:

```toml
[step1]
type = "Command"
command_name = "echo 'First step'"
# depends_on = [] (implicit - first node has no dependencies)

[step2]
type = "Command"
command_name = "echo 'Second step'"
# depends_on = ["step1"] (implicit - depends on previous node)

[step3]
type = "Command"
command_name = "echo 'Third step'"
# depends_on = ["step2"] (implicit - depends on previous node)
```

**Simplified Single Dependencies**
Use a string instead of a list for single dependencies:

```toml
[deploy]
type = "Command"
command_name = "deploy.sh"
depends_on = "build"  # Same as depends_on = ["build"]
```

**Special Keywords**
- `depends_on = "^"` - Depend on the previous node (explicit version of implicit behavior)
- `depends_on = "*"` - Depend on all previous nodes

```toml
[step1]
type = "Command"
command_name = "echo 'Step 1'"

[step2]
type = "Command"
command_name = "echo 'Step 2'"
depends_on = "^"  # Explicit dependency on step1

[final]
type = "Command"
command_name = "echo 'Final step'"
depends_on = "*"  # Depends on both step1 and step2
```

**Traditional Explicit Dependencies**
You can still specify explicit dependencies as before:

```toml
[complex_node]
type = "Command"
command_name = "complex.sh"
depends_on = ["step1", "step3", "other_node"]  # Multiple explicit dependencies
```

#### Manual Node

```toml
[approve]
type         = "Manual"
prompt_after = "Proceed with deployment?"
description  = """
Critical manual approval checkpoint for production deployment.
This step ensures proper authorization and readiness assessment
before proceeding with changes that affect live systems.
"""
depends_on   = ["setup"]
skip         = false
critical     = true
```

#### Command Node

```toml
[build]
type         = "Command"
command_name = "make build"
description  = """
Build application artifacts with all dependencies and optimizations.
This step compiles source code, resolves dependencies, and creates
deployable packages ready for testing and deployment.
"""
depends_on   = ["setup"]
timeout      = 300
```

#### Function Node

Function nodes use plugin-based execution:

```toml
[slack_notify]
type = "Function"
plugin = "slack"                    # Plugin name
function = "send_message"           # Function within plugin
function_params = {
    channel = "#ops",
    message = "Deployment complete!"
}
plugin_config = {
    webhook_url = "${SLACK_WEBHOOK}",
    timeout = 30
}
description = "Notify team via Slack"
depends_on = ["build", "tests"]
```

**Built-in Python functions:**
```toml
[notify_completion]
type = "Function"
plugin = "python"
function = "notify"
function_params = { message = "Deployment complete!" }
description = "Send notification"
depends_on = ["build", "tests"]
```

### Conditional Dependencies and Branching

Playbook supports sophisticated conditional logic for complex workflow patterns:

#### Shorthand Conditional Dependencies
```toml
[deploy_success]
type = "Command"
command_name = "echo 'Deployment successful'"
depends_on = ["deploy:success"]  # Only run if deploy succeeded

[rollback_deployment]
type = "Command"
command_name = "rollback.sh"
depends_on = ["deploy:failure"]  # Only run if deploy failed

[cleanup]
type = "Command"
command_name = "cleanup.sh"
depends_on = ["deploy:success", "rollback:success"]  # Run after either succeeds
```

#### Advanced Conditional Logic with Jinja2
```toml
[variables]
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }
SKIP_TESTS = { default = false, type = "bool" }

[security_scan]
type = "Command"
command_name = "security-scan --strict"
depends_on = ["build"]
when = "{{ ENVIRONMENT == 'prod' }}"  # Only run for production

[run_tests]
type = "Command"
command_name = "npm test"
depends_on = ["build"]
when = "{{ not SKIP_TESTS and ENVIRONMENT in ['staging', 'prod'] }}"

[deploy]
type = "Command"
command_name = "deploy.sh {{ENVIRONMENT}}"
depends_on = ["build"]
when = "{{ (SKIP_TESTS or has_succeeded('run_tests')) and (ENVIRONMENT != 'prod' or has_succeeded('security_scan')) }}"
```

### Variables

Make workflows dynamic with variable support. Define variables in a `[variables]` section:

```toml
[variables]
APP_NAME = { default = "myapp", description = "Application name" }
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"] }
VERSION = { default = "latest", description = "Version to deploy" }
TIMEOUT = { default = 300, type = "int", min = 60, max = 3600 }

[runbook]
title = "Deploy {{APP_NAME}} to {{ENVIRONMENT}}"
description = "Deploy {{APP_NAME}} version {{VERSION}}"
# ... rest of runbook metadata

[deploy]
type = "Command"
command_name = "kubectl apply -f {{APP_NAME}}-{{ENVIRONMENT}}.yaml"
description = "Deploy {{APP_NAME}} version {{VERSION}} to {{ENVIRONMENT}}"
timeout = "{{TIMEOUT}}"
critical = "{% if ENVIRONMENT == 'prod' %}true{% else %}false{% endif %}"
depends_on = []
```

#### Variable Sources (Priority Order)
1. **CLI arguments**: `--var ENVIRONMENT=prod --var VERSION=1.2.3`
2. **Variable files**: `--vars-file production.vars.toml`
3. **Environment variables**: `--vars-env PLAYBOOK_VAR_` (loads PLAYBOOK_VAR_*)
4. **Interactive prompts**: Automatic prompts for missing required variables
5. **Defaults**: From variable definitions in workflow file

#### Interactive Variable Prompts
Playbook automatically prompts for missing required variables during execution:
```bash
# Interactive mode (default) - prompts for missing variables
playbook run deploy.playbook.toml --var ENVIRONMENT=prod
# Will prompt: "Enter value for VERSION (Version to deploy) [latest]: "

# Non-interactive mode - fails if required variables are missing
playbook run deploy.playbook.toml --var ENVIRONMENT=prod --no-interactive-vars
```

#### Jinja2 Features
- **Simple substitution**: `{{VAR_NAME}}`
- **Defaults**: `{{VAR_NAME|default('fallback')}}`
- **Filters**: `{{APP_NAME|upper}}`, `{{SERVICES|join(', ')}}`
- **Conditionals**: `{% if ENVIRONMENT == 'prod' %}critical{% endif %}`
- **Loops**: `{% for service in SERVICES %}deploy {{service}} && {% endfor %}`

#### Automatic Type Conversion
Playbook automatically converts template variables to the expected parameter types:

```toml
[variables]
TIMEOUT = { default = 300, type = "int" }
ENABLED = { default = true, type = "bool" }

[sleep_step]
type = "Function"
plugin = "python"
function = "sleep"
function_params = { seconds = "{{TIMEOUT}}" }  # String "300" → int 300

[notification]
type = "Function"
plugin = "example"
function = "send_alert"
function_params = {
    message = "Alert for {{APP_NAME}}",  # Stays as string
    urgent = "{{ENABLED}}"               # String "true" → bool true
}
```

**Supported conversions:**
- `int`: `"42"` → `42`
- `float`: `"3.14"` → `3.14`
- `bool`: `"true"/"false"`, `"1"/"0"`, `"yes"/"no"` → `true`/`false`
- `list`: `'["a","b"]'` → `["a", "b"]` (JSON parsing)
- `dict`: `'{"key":"value"}'` → `{"key": "value"}` (JSON parsing)

## 🔌 Plugin System

Playbook features a powerful plugin system that allows external packages to extend functionality through a standardized interface.

### Using Plugins

#### Plugin Installation
```bash
# Install plugins from PyPI
pip install playbook-slack playbook-aws playbook-http

# List available plugins
playbook info --plugins
```

#### Plugin Discovery
Plugins are automatically discovered through Python entry points. Once installed, they're immediately available in workflows without configuration.

#### Plugin Configuration

Plugins support both global and per-node configuration:

```toml
# Global plugin configuration (applies to all uses)
[runbook.plugin_config.slack]
default_webhook = "${SLACK_WEBHOOK}"
timeout = 30

# Per-node plugin configuration (overrides global)
[notify_success]
type = "Function"
plugin = "slack"
function = "send_message"
function_params = { channel = "#ops", message = "Success!" }
plugin_config = { webhook_url = "${SUCCESS_WEBHOOK}" }  # Node-specific override
```

### Plugin Development

For an example plugin implementation, see the built-in Python plugin in `playbook/plugins/python_plugin.py` or
the full-blown example in `playbook-slack-plugin`.

#### When to Create a Plugin

Create a separate plugin when you need:
- **External service integrations** (APIs, databases, cloud services)
- **Specialized data processing** or transformations
- **Domain-specific functionality** unique to your use case

The built-in Python plugin provides basic utilities (`notify`, `sleep`, `throw`) as demonstrations. 

#### Creating a Plugin

External developers can create plugins by implementing the `Plugin` interface:

```python
# my_plugin/plugin.py
from playbook.domain.plugins import Plugin, PluginMetadata, FunctionSignature, ParameterDef

class MyPlugin(Plugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            author="Your Name",
            description="Custom functionality for Playbook",
            functions={
                "my_function": FunctionSignature(
                    name="my_function",
                    description="Does something useful",
                    parameters={
                        "input": ParameterDef(
                            type="str",
                            required=True,
                            description="Input parameter"
                        )
                    }
                )
            }
        )

    def initialize(self, config):
        self.config = config

    def execute(self, function_name, params):
        if function_name == "my_function":
            return f"Processed: {params['input']}"

    def cleanup(self):
        pass
```

#### Plugin Registration

Register your plugin via setuptools entry points in `pyproject.toml`:

```toml
[project.entry-points."playbook.plugins"]
my-plugin = "my_plugin.plugin:MyPlugin"
```

#### Plugin Distribution

```bash
# Package and distribute
pip install build
python -m build
twine upload dist/*

# Install and use
pip install my-plugin
```

### Available Plugins

#### Built-in Plugins
- **python**: Built-in utility functions (notify, sleep, throw) for common workflow operations

#### Community Plugins
Popular plugins available on PyPI:
- **playbook-slack**: Slack notifications and interactions
- **playbook-aws**: AWS service integrations
- **playbook-http**: HTTP requests and API calls
- **playbook-k8s**: Kubernetes operations
- **playbook-git**: Git repository operations

*Note: Plugin availability depends on community contributions*

### Details and Specification
More info: [DAG.md](doc/DAG.md)

## ⚡ Retry and Error Handling

Playbook provides robust error handling and retry capabilities for resilient workflow execution:

### Interactive Retry Functionality
When a node fails during execution, Playbook offers interactive choices:
- **Retry (r)**: Attempt the failed node again (tracks attempt number)
- **Skip (s)**: Skip the failed node and continue (only for non-critical nodes)
- **Abort (a)**: Stop the entire workflow execution

```bash
# Configure maximum retry attempts (default: 3)
playbook run workflow.playbook.toml --max-retries 5

# Resume failed workflows from specific nodes
playbook resume workflow.playbook.toml <run_id> --max-retries 3
```

### Attempt Tracking
- Each retry gets a new attempt number with full state persistence
- Execution history is maintained for debugging and analysis
- Critical nodes cannot be skipped, only retried or aborted
- Progress tracking correctly handles retry loops

### Node Criticality
```toml
[critical_deployment]
type = "Command"
command_name = "deploy-production.sh"
critical = true  # Cannot be skipped if it fails
depends_on = ["tests"]

[optional_notification]
type = "Function"
plugin = "slack"
function = "send_message"
critical = false  # Can be skipped if it fails
depends_on = ["critical_deployment"]
```

## 🔄 Workflow State and Resume Behavior

### Workflow States

Workflows can be in one of four states:

| State | Description |
|-------|-------------|
| **RUNNING** | Workflow is currently executing |
| **OK** | Workflow completed successfully |
| **NOK** | Workflow failed (critical node failure or all retries exhausted) |
| **ABORTED** | Workflow was interrupted or aborted by user |

### Resume Behavior

**Only ABORTED workflows can be resumed.** Other states require different actions:

| Scenario | Resulting State | Can Resume? | Action Required |
|----------|-----------------|-------------|-----------------|
| **CTRL-C during execution** | ABORTED | ✅ Yes | `playbook resume <file> [<run_id>]` |
| **User selects "Abort" on failure** | ABORTED | ✅ Yes | `playbook resume <file> [<run_id>]` |
| **Critical node failure** | NOK | ❌ No | Start new run with `playbook run <file>` |
| **Max retries exhausted** | NOK | ❌ No | Start new run with `playbook run <file>` |
| **Workflow completes successfully** | OK | ❌ No | N/A - workflow is complete |
| **Process killed (SIGKILL)** | RUNNING | ❌ No | Orphaned - requires manual intervention* |
| **Computer reboot/crash** | RUNNING | ❌ No | Orphaned - requires manual intervention* |

\* **Orphaned workflows:** External kills leave workflows in RUNNING state. These cannot be resumed automatically.
Options:
1. Start a new run
2. Use `playbook set-status <file> <run_id> ABORTED` to mark as aborted, then resume

### Resuming Aborted Workflows

When resuming an aborted workflow, execution continues from the point of interruption:

```bash
# Resume latest aborted run (auto-detects run_id)
playbook resume workflow.playbook.toml

# Resume specific run by ID
playbook resume workflow.playbook.toml 42

# Resume with updated variables
playbook resume workflow.playbook.toml 42 --var VERSION=1.2.4

# Resume with different retry configuration
playbook resume workflow.playbook.toml 42 --max-retries 5
```

**Note:** Completed nodes are skipped on resume. Only failed, pending, or not-yet-executed nodes will run.

## ⚙️ Configuration Management

Playbook features a flexible configuration system with environment-based settings:

### Configuration Discovery
Playbook searches for configuration files in this order:
1. **Local**: `./playbook.toml` (project-specific)
2. **User**: `~/.config/playbook/config.toml` (user-specific)
3. **System**: `/etc/playbook/config.toml` (system-wide)

### Environment-Based Configuration
```bash
# Set environment for configuration selection
export PLAYBOOK_ENV=production  # development, testing, production

# Direct configuration file override
export PLAYBOOK_CONFIG=/path/to/custom.toml
```

### Configuration Sections
```toml
[database]
path = "~/.config/playbook/run.db"
timeout = 30
backup_enabled = true
backup_count = 5

[execution]
default_timeout = 300
max_retries = 3
interactive_timeout = 1800
parallel_execution = false

[logging]
level = "INFO"
file_path = ""  # Empty = console only
max_size_mb = 10
backup_count = 3

[ui]
progress_style = "bar"
color_theme = "auto"  # auto, light, dark, none
show_timestamps = true
compact_output = false
```

### Environment Variable Overrides
```bash
# Override specific configuration values
export PLAYBOOK_DB_PATH="/custom/path/run.db"
export PLAYBOOK_LOG_LEVEL="DEBUG"
export PLAYBOOK_MAX_RETRIES=5
```

### Configuration Management Commands
```bash
# Show current configuration
playbook config --show

# Initialize environment-specific configuration
playbook config --init production

# Validate configuration
playbook config --validate

# Generate configuration template
playbook config --template config-template.toml
```

## 🧑‍💻 CLI Usage

### Create a new runbook

```bash
playbook create --title "My Workflow" --author "Your Name"
```

### Validate a runbook

```bash
# Basic validation
playbook validate path/to/runbook.playbook.toml

# Check variable requirements
playbook validate path/to/runbook.playbook.toml --check-vars

# Validate with specific variables
playbook validate path/to/runbook.playbook.toml --var ENVIRONMENT=prod
```

### Execute a workflow

```bash
# Basic execution (prompts for required variables)
playbook run path/to/runbook.playbook.toml

# With CLI variables
playbook run path/to/runbook.playbook.toml --var ENVIRONMENT=prod --var VERSION=1.2.3

# With variable file
playbook run path/to/runbook.playbook.toml --vars-file production.vars.toml

# With environment variables (loads PLAYBOOK_VAR_*)
export PLAYBOOK_VAR_ENVIRONMENT=prod
playbook run path/to/runbook.playbook.toml --vars-env PLAYBOOK_VAR_

# With retry configuration
playbook run path/to/runbook.playbook.toml --max-retries 5

# Non-interactive execution
playbook run path/to/runbook.playbook.toml --vars-file vars.toml --no-interactive-vars

# Custom state database path
playbook run path/to/runbook.playbook.toml --state-path /custom/path/run.db
```

### Resume an aborted workflow

```bash
# Resume latest aborted run (auto-detects run_id)
playbook resume path/to/runbook.playbook.toml

# Resume specific aborted run by ID
playbook resume path/to/runbook.playbook.toml 42

# Resume with updated variables and retry configuration
playbook resume path/to/runbook.playbook.toml 42 --var VERSION=1.2.4 --max-retries 5

# Resume with variable file
playbook resume path/to/runbook.playbook.toml 42 --vars-file updated-vars.toml
```

**Note:** Only ABORTED workflows can be resumed. NOK (failed) workflows require a new run.

### Manually set workflow status

```bash
# Fix orphaned workflow (RUNNING -> ABORTED after system crash/reboot)
playbook set-status path/to/runbook.playbook.toml 42 ABORTED

# Skip confirmation prompt
playbook set-status path/to/runbook.playbook.toml 42 ABORTED --force

# Custom database path
playbook set-status path/to/runbook.playbook.toml 42 NOK --state-path /custom/run.db
```

**Use cases:**
- Fix orphaned RUNNING workflows after system crash or reboot
- Manually mark workflows as completed or failed
- Reset workflow state for testing

**Warning:** This command directly modifies workflow state in the database. Use with caution in production environments.

### View DAG visualization

```bash
# View and save DAG as PNG (requires Graphviz)
playbook view-dag path/to/runbook.playbook.toml

# Also save DOT file
playbook view-dag path/to/runbook.playbook.toml --keep-dot

# For automation (no auto-open)
playbook view-dag path/to/runbook.playbook.toml --no-open
```

**Note:** DAG visualization requires [Graphviz](https://graphviz.org/download/) to be installed:
- macOS: `brew install graphviz`
- Ubuntu/Debian: `sudo apt-get install graphviz`
- CentOS/RHEL: `sudo yum install graphviz`

### Show run statistics and plugin information

```bash
# Show general information
playbook info

# Show specific workflow runs
playbook show "Example Workflow"

# List available plugins and their functions
playbook info --plugins
```


## 📂 State and Storage

- SQLite DB at `~/.config/playbook/run.db` by default
- Run and node execution state is persisted
- Allows resuming failed runs or inspecting previous ones


## 🧩 Extending and Plugin Ecosystem

### Creating Plugins

**Plugin-Only Architecture**: Playbook uses a strict plugin-only architecture. All custom functionality must be implemented as plugins that adhere to the plugin interface. There is no mechanism to execute arbitrary Python code dynamically.

The recommended way to extend Playbook functionality is through plugins:

1. **Create a plugin package**: Implement the `Plugin` interface
2. **Register via entry points**: Use `playbook.plugins` entry point group
3. **Distribute**: Publish to PyPI or install locally
4. **Use in workflows**: Reference by plugin name in TOML files

### Plugin Development Best Practices

- **Parameter validation**: Define comprehensive `ParameterDef` schemas
- **Error handling**: Provide clear, actionable error messages
- **Documentation**: Include examples and detailed function descriptions
- **Testing**: Write comprehensive tests for all plugin functions
- **Security**: Validate all inputs and handle secrets properly

### Core System Extension

For core system modifications:
- **Infrastructure adapters**: New persistence/visualization backends
- **Domain extensions**: New node types or workflow features
- **Service layer**: New execution strategies or orchestration logic
- **Architecture**: Follow hexagonal architecture boundaries

### Plugin Naming Conventions

- **Package names**: `playbook-{service}` (e.g., `playbook-slack`)
- **Entry point names**: Short, descriptive (e.g., `slack`, `aws`, `http`)
- **Function names**: Action-oriented (e.g., `send_message`, `create_instance`)

### Contributing

- Plugin contributions welcome via separate packages
- Core system contributions via pull requests
- Documentation improvements always appreciated


## 📚 Complete Example Workflow

Example showcasing modern Playbook features with variables, conditional dependencies, and multi-line descriptions:

```toml
[variables]
ENVIRONMENT = { required = true, choices = ["dev", "staging", "prod"], description = "Target environment" }
APP_NAME = { default = "myapp", description = "Application name" }
SKIP_TESTS = { default = false, type = "bool", description = "Skip test execution" }

[runbook]
title = "{{APP_NAME}} Deployment Pipeline"
description = """
Comprehensive deployment workflow for {{APP_NAME}} with environment-aware validation.
This pipeline adapts its behavior based on target environment, providing appropriate
security scanning for production and flexible testing options for all environments.
"""
version = "1.0.0"
author = "Platform Team"
created_at = "2025-01-20T12:00:00Z"

[build_app]
type = "Command"
command_name = "npm run build"
description = """
Build the application with all dependencies and optimizations.
This step ensures consistent, reproducible builds across all environments
while preparing deployable artifacts ready for testing and deployment.
"""
depends_on = []

[run_tests]
type = "Command"
command_name = "npm test"
description = """
Execute comprehensive test suite including unit and integration tests.
This validation step ensures code quality and functionality before deployment,
but can be conditionally skipped for emergency deployments when needed.
"""
depends_on = ["build_app"]
when = "{{ not SKIP_TESTS }}"

[security_scan]
type = "Command"
command_name = "npm audit --audit-level high"
description = """
Perform mandatory security vulnerability scan for production deployments.
This critical validation ensures compliance with security policies and
identifies potential risks before production release.
"""
depends_on = ["build_app"]
when = "{{ ENVIRONMENT == 'prod' }}"
critical = true

[deploy_application]
type = "Command"
command_name = "deploy.sh {{ENVIRONMENT}} --app={{APP_NAME}}"
description = """
Deploy {{APP_NAME}} to the {{ENVIRONMENT}} environment with monitoring.
This step handles environment-specific configurations, secrets management,
and progressive rollout while maintaining service availability.
"""
depends_on = ["build_app"]
when = "{{ (SKIP_TESTS or has_succeeded('run_tests')) and (ENVIRONMENT != 'prod' or has_succeeded('security_scan')) }}"

[health_check]
type = "Command"
command_name = "curl -f https://{{APP_NAME}}-{{ENVIRONMENT}}.company.com/health"
description = """
Verify deployment health and application functionality post-deployment.
This validation ensures the application is operational and ready to serve
traffic before considering the deployment complete.
"""
depends_on = ["deploy_application"]
when = "{{ has_succeeded('deploy_application') }}"

[rollback_on_failure]
type = "Command"
command_name = "rollback.sh {{ENVIRONMENT}}"
description = """
Automatically rollback deployment if health checks fail.
This safety mechanism restores the previous stable version to minimize
service disruption and maintain system reliability.
"""
depends_on = ["health_check"]
when = "{{ has_failed('health_check') }}"

[notify_success]
type = "Function"
plugin = "python"
function = "notify"
function_params = { message = "✅ {{APP_NAME}} deployed successfully to {{ENVIRONMENT}}" }
description = """
Send success notification to stakeholders and monitoring systems.
This communication provides visibility into successful deployments and
maintains operational awareness across development and operations teams.
"""
depends_on = ["health_check"]
when = "{{ has_succeeded('health_check') }}"

[notify_failure]
type = "Function"
plugin = "python"
function = "notify"
function_params = { message = "❌ {{APP_NAME}} deployment to {{ENVIRONMENT}} failed" }
description = """
Alert teams about deployment failure and trigger incident response.
This notification ensures rapid awareness of deployment issues and
enables quick remediation to restore service functionality.
"""
depends_on = ["health_check", "rollback_on_failure"]
when = "{{ has_failed('health_check') }}"
```


## 🧪 Testing

To run and validate your workflow logic, use:

```bash
make test  # or
pytest tests/
```

