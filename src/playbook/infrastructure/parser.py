from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..domain.models import Runbook, VariableDefinition
from .variables import VariableManager


class RunbookParser:
    def __init__(self, variable_manager: VariableManager | None = None) -> None:
        self.variable_manager = variable_manager

    def parse(
        self,
        file_path: str | Path,
        variables: dict[str, Any] | None = None,
    ) -> Runbook:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Runbook file not found: {file_path}")
        if not path.name.endswith(".playbook.toml"):
            raise ValueError("Runbook file must have a .playbook.toml extension")

        raw_content = path.read_bytes()
        try:
            initial_data = tomllib.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"Cannot parse runbook TOML: {error}") from error

        if initial_data.get("schema_version") != 2:
            raise ValueError(
                "Unsupported or missing schema_version. Convert this workflow with "
                f"'playbook migrate {path}'."
            )

        definitions = self._parse_variable_definitions(
            initial_data.get("variables", {})
        )
        resolved_variables = self._resolve_variables(definitions, variables)

        rendered_content = raw_content.decode("utf-8")
        if self.variable_manager is not None and resolved_variables:
            rendered_content = self.variable_manager.substitute_in_string(
                rendered_content,
                resolved_variables,
            )

        try:
            data = tomllib.loads(rendered_content)
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Cannot parse rendered runbook TOML: {error}") from error

        metadata = data.get("runbook")
        if not isinstance(metadata, dict):
            raise ValueError("Missing required [runbook] section")
        steps = data.get("steps")
        if not isinstance(steps, list):
            raise ValueError("Missing required [[steps]] entries")

        try:
            return Runbook.model_validate(
                {
                    "schema_version": data["schema_version"],
                    **metadata,
                    "steps": steps,
                    "variable_definitions": definitions,
                    "variables": resolved_variables,
                    "source_path": str(path.resolve()),
                    "definition_hash": hashlib.sha256(raw_content).hexdigest(),
                }
            )
        except ValidationError as error:
            messages = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()
            )
            raise ValueError(f"Invalid runbook: {messages}") from error

    def get_variable_definitions(
        self, file_path: str | Path
    ) -> dict[str, VariableDefinition]:
        path = Path(file_path)
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"Cannot read variable definitions: {error}") from error
        if data.get("schema_version") != 2:
            raise ValueError(
                "Unsupported or missing schema_version. Use 'playbook migrate'."
            )
        return self._parse_variable_definitions(data.get("variables", {}))

    @staticmethod
    def _parse_variable_definitions(
        raw_definitions: object,
    ) -> dict[str, VariableDefinition]:
        if not isinstance(raw_definitions, dict):
            raise ValueError("[variables] must be a table")
        definitions: dict[str, VariableDefinition] = {}
        for name, raw_definition in raw_definitions.items():
            if not isinstance(name, str):
                raise ValueError("Variable names must be strings")
            try:
                if isinstance(raw_definition, dict):
                    definitions[name] = VariableDefinition.model_validate(
                        raw_definition
                    )
                else:
                    definitions[name] = VariableDefinition(default=raw_definition)
            except ValidationError as error:
                raise ValueError(
                    f"Invalid variable definition '{name}': {error}"
                ) from error
        return definitions

    def _resolve_variables(
        self,
        definitions: dict[str, VariableDefinition],
        provided: dict[str, Any] | None,
    ) -> dict[str, Any]:
        defaults = {
            name: definition.default
            for name, definition in definitions.items()
            if definition.default is not None
        }
        if self.variable_manager is None:
            return {**defaults, **(provided or {})}
        resolved = self.variable_manager.merge_variables(
            cli_vars=provided,
            defaults=defaults,
        )
        self.variable_manager.validate_variables(resolved, definitions)
        missing = self.variable_manager.get_missing_required(definitions, resolved)
        if missing:
            resolved.update(
                self.variable_manager.prompt_for_missing_variables(missing, definitions)
            )
            self.variable_manager.validate_variables(resolved, definitions)
        return resolved
