# Examples

All examples use schema version 2 and execute `[[steps]]` in file order.

- `simple_bash_commands.playbook.toml`: manual preparation, a command, and
  operator verification.
- `plugin.playbook.toml`: built-in Python plugin functions.
- `variables/deploy.playbook.toml`: typed variables, a secret, and an optional
  Boolean-controlled step.

Validate before running:

```bash
playbook validate examples/simple_bash_commands.playbook.toml
playbook run examples/simple_bash_commands.playbook.toml
```

Override variables from the CLI or a variable file:

```bash
playbook run examples/variables/deploy.playbook.toml \
  --vars-file examples/variables/development.vars.toml \
  --var VERSION=main
```

The examples use harmless placeholder commands. Replace them with commands
appropriate for your environment only after reviewing their effects.
