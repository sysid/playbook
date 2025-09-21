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
- **Variable support** with Jinja2 templating for dynamic workflows
- **Plugin system** for extensible functionality with external packages
- Manual, command, and function nodes
- Plugin-based function execution
- Rich CLI interface with progress display and user interaction
- Execution state stored in **SQLite** (resumable)
- DAG visualization with **Graphviz**
- Built-in statistics for workflow runs
- Extensible architecture following **Hexagonal Architecture**


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
type         = "Manual"
prompt_after = "Proceed with deployment?"
description  = """This step requires manual approval."""
depends_on   = ["setup"]
skip         = false
critical     = true
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
4. **Defaults**: From variable definitions in workflow file

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

# Non-interactive execution
playbook run path/to/runbook.playbook.toml --vars-file vars.toml --no-interactive-vars
```

### Resume a failed workflow

```bash
playbook resume path/to/runbook.playbook.toml 42
```

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
make test  # or
pytest tests/
```

