# Prompt for generating a Playbook workflow

Generate a schema-version-2 Playbook TOML file for the procedure described by
the user.

Constraints:

1. Start with `schema_version = 2`.
2. Add `[runbook]` with a stable kebab-case `id`, concise `title`, purpose,
   version, and owner.
3. Express the procedure as ordered `[[steps]]`. File order is execution order.
4. Use only lowercase step types: `manual`, `command`, and `function`.
5. Give every step a stable ID, short name, and operator-focused instructions.
6. Mark safety or prerequisite steps as required. Mark convenience steps
   `required = false`.
7. Do not generate dependencies, DAGs, branches, parallel execution, or complex
   conditions.
8. If a step is controlled by configuration, use `enabled_if` referencing a
   non-secret Boolean variable.
9. Mark sensitive variables `secret = true`. Never place literal secrets in the
   workflow.
10. Use `verify` after commands or functions when human judgment is required.
11. Prefer read-only checks and explicit abort points before commands that
    change state.
12. Return only the TOML document, without Markdown fences.

Field names:

- Manual: `instructions`, optional `prompt`.
- Command: `command`, optional `interactive`, `timeout_seconds`, `verify`.
- Function: `plugin`, `function`, optional `params`, `config`, `verify`.

If requirements are ambiguous or a command could be destructive, do not invent
it. Generate a required manual step explaining what must be decided.
