from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import tomlkit


class LegacyRunbookMigrator:
    _simple_condition = re.compile(r"^\s*\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}\s*$")

    def migrate(self, file_path: str | Path) -> str:
        path = Path(file_path)
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError(
                f"Cannot parse legacy runbook '{path}': {error}"
            ) from error

        if data.get("schema_version") == 2:
            raise ValueError(f"Runbook '{path}' already uses schema version 2")
        metadata = data.pop("runbook", None)
        if not isinstance(metadata, dict):
            raise ValueError("Legacy runbook is missing [runbook]")
        variables = data.pop("variables", {})
        nodes = {
            node_id: node for node_id, node in data.items() if isinstance(node, dict)
        }
        order, referenced = self._execution_order(nodes)

        document = tomlkit.document()
        document.add("schema_version", tomlkit.item(2))
        document.add(tomlkit.nl())

        runbook = tomlkit.table()
        runbook.add("id", path.name.removesuffix(".playbook.toml"))
        runbook.add("title", str(metadata.get("title", path.stem)))
        for key in ("description", "version", "author"):
            if value := metadata.get(key):
                runbook.add(key, value)
        document.add("runbook", runbook)

        if variables:
            document.add(tomlkit.nl())
            document.add("variables", variables)

        steps = tomlkit.aot()
        for node_id in order:
            steps.append(self._convert_node(node_id, nodes[node_id], referenced))
        document.add(tomlkit.nl())
        document.add("steps", steps)
        return tomlkit.dumps(document)

    def migrate_to(
        self,
        file_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        output = Path(output_path)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {output}")
        output.write_text(self.migrate(file_path))
        return output

    def _execution_order(
        self,
        nodes: dict[str, dict[str, Any]],
    ) -> tuple[list[str], set[str]]:
        declaration_order = list(nodes)
        dependencies: dict[str, list[str]] = {}
        referenced: set[str] = set()
        for index, node_id in enumerate(declaration_order):
            raw_dependencies = nodes[node_id].get("depends_on")
            if raw_dependencies is None:
                normalized = declaration_order[index - 1 : index]
            elif isinstance(raw_dependencies, str):
                normalized = [raw_dependencies] if raw_dependencies else []
            elif isinstance(raw_dependencies, list):
                if not all(
                    isinstance(dependency, str) for dependency in raw_dependencies
                ):
                    raise ValueError(f"step '{node_id}': dependencies must be strings")
                normalized = cast(list[str], raw_dependencies)
            else:
                raise ValueError(
                    f"step '{node_id}': depends_on must be a string or list"
                )

            expanded: list[str] = []
            for dependency in normalized:
                if dependency == "^":
                    expanded.extend(declaration_order[index - 1 : index])
                elif dependency == "*":
                    expanded.extend(declaration_order[:index])
                elif isinstance(dependency, str) and ":" in dependency:
                    raise ValueError(
                        f"step '{node_id}': cannot migrate conditional dependency "
                        f"'{dependency}'"
                    )
                else:
                    expanded.append(dependency)
            unknown = [dependency for dependency in expanded if dependency not in nodes]
            if unknown:
                raise ValueError(
                    f"step '{node_id}': unknown dependencies {', '.join(unknown)}"
                )
            dependencies[node_id] = list(dict.fromkeys(expanded))
            referenced.update(expanded)

        followers: dict[str, list[str]] = defaultdict(list)
        indegree = {
            node_id: len(dependencies[node_id]) for node_id in declaration_order
        }
        for node_id, node_dependencies in dependencies.items():
            for dependency in node_dependencies:
                followers[dependency].append(node_id)

        ready = [node_id for node_id in declaration_order if indegree[node_id] == 0]
        ordered: list[str] = []
        while ready:
            node_id = ready.pop(0)
            ordered.append(node_id)
            for follower in followers[node_id]:
                indegree[follower] -= 1
                if indegree[follower] == 0:
                    ready.append(follower)
                    ready.sort(key=declaration_order.index)
        if len(ordered) != len(nodes):
            raise ValueError("Legacy runbook contains a dependency cycle")
        return ordered, referenced

    def _convert_node(
        self,
        node_id: str,
        node: dict[str, Any],
        referenced: set[str],
    ) -> Any:
        legacy_type = node.get("type")
        step = tomlkit.table()
        step.add("id", node_id)
        if legacy_type == "Manual":
            step.add("type", "manual")
        elif legacy_type == "Command":
            step.add("type", "command")
        elif legacy_type == "Function":
            step.add("type", "function")
        else:
            raise ValueError(f"step '{node_id}': unknown type '{legacy_type}'")

        if name := node.get("name"):
            step.add("name", name)
        if description := node.get("description"):
            step.add("instructions", description)
        step.add(
            "required",
            bool(node.get("critical", False) or node_id in referenced),
        )
        if node.get("skip", False):
            step.add("enabled", False)

        condition = node.get("when")
        if condition and condition != "true":
            match = self._simple_condition.fullmatch(str(condition))
            if match is None:
                raise ValueError(
                    f"step '{node_id}': cannot migrate complex condition '{condition}'"
                )
            step.add("enabled_if", match.group(1))

        if legacy_type == "Manual":
            if prompt := node.get("prompt_after"):
                step.add("prompt", prompt)
        elif legacy_type == "Command":
            command = node.get("command_name")
            if not command:
                raise ValueError(f"step '{node_id}': command_name is required")
            step.add("command", command)
            if node.get("interactive", False):
                step.add("interactive", True)
            if timeout := node.get("timeout"):
                step.add("timeout_seconds", timeout)
            if verify := node.get("prompt_after"):
                step.add("verify", verify)
        else:
            for old_name, new_name in (
                ("plugin", "plugin"),
                ("function", "function"),
                ("function_params", "params"),
                ("plugin_config", "config"),
            ):
                if old_name in node:
                    step.add(new_name, node[old_name])
            if "plugin" not in node or "function" not in node:
                raise ValueError(f"step '{node_id}': plugin and function are required")
            if verify := node.get("prompt_after"):
                step.add("verify", verify)
        return step
