# Playbook Examples

This directory contains example workflows demonstrating various Playbook features.

## Python Plugin Examples

### plugin.playbook.toml
A comprehensive demonstration of Python plugin functionality including:
- Built-in notification functions
- Sleep/delay operations
- Built-in utility functions
- Variable substitution with Jinja2 templating
- Manual approval steps for interactive workflows

**Features demonstrated:**
- `notify` function for user notifications
- `sleep` function for workflow delays
- `throw` function for testing error handling
- Variable templating and substitution

**Run with:**
```bash
playbook run examples/plugin.playbook.toml
```

### plugin-auto.playbook.toml
A fully automated version demonstrating the same Python plugin features without manual steps, suitable for CI/CD or automated environments.

**Run with:**
```bash
# Provide approval for each step
echo -e "y\ny\ny\ny" | playbook run examples/plugin-auto.playbook.toml --no-interactive-vars
```

## Usage Tips

1. **Interactive Mode**: Most workflows include approval steps. Respond with 'y' to continue.

2. **Non-Interactive Mode**: Use `--no-interactive-vars` to avoid variable prompts, and pipe responses for approval steps:
   ```bash
   echo "y" | playbook run workflow.playbook.toml --no-interactive-vars
   ```

3. **Variable Customization**: Override default variables:
   ```bash
   playbook run plugin.playbook.toml --var APP_NAME=my-app --var SLEEP_DURATION=3
   ```

4. **Validation**: Always validate workflows before running:
   ```bash
   playbook validate examples/plugin.playbook.toml
   ```

## Plugin System Benefits

The examples showcase the plugin-only architecture benefits:

- **Consistency**: All functions use the same `plugin` + `function` syntax
- **Extensibility**: Easy to add new functions via plugins
- **Type Safety**: Parameter validation through plugin metadata
- **Documentation**: Self-documenting functions with schemas
- **Distribution**: Plugins can be distributed as separate PyPI packages

## Variables Examples

See the `variables/` directory for advanced variable templating examples.
