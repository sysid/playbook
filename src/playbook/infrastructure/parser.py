# src/playbook/infrastructure/parser.py
import logging
import tomllib  # Use tomllib instead of tomli
from datetime import datetime
from pathlib import Path
from typing import Dict, Union, Optional, Any

from pydantic import ValidationError

from ..domain.models import (
    Runbook,
    NodeType,
    ManualNode,
    FunctionNode,
    CommandNode,
    VariableDefinition,
)
from .variables import VariableManager, VariableValidationError
from ..domain.exceptions import ConfigurationError
from .conditions import parse_dependencies
import re

logger = logging.getLogger(__name__)


class RunbookParser:
    """Parser for runbook TOML files with variable support"""

    def __init__(self, variable_manager: Optional[VariableManager] = None):
        """Initialize parser with optional variable manager.

        Args:
            variable_manager: Variable manager for template processing
        """
        self.variable_manager = variable_manager

    def parse(
        self, file_path: str, variables: Optional[Dict[str, Any]] = None
    ) -> Runbook:
        """Parse a runbook file with optional variable substitution.

        Args:
            file_path: Path to the runbook file
            variables: Variables to substitute in the template

        Returns:
            Parsed runbook object

        Raises:
            FileNotFoundError: If runbook file doesn't exist
            ValueError: If required sections or fields are missing
            VariableValidationError: If variable validation fails
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Runbook file not found: {file_path}")

        if not str(path).endswith(".playbook.toml"):
            raise ValueError("Runbook file must have a .playbook.toml extension")

        # Read the file content first
        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Extract and process variables section if it exists
        variable_definitions = {}
        final_variables = {}

        # First, do a quick parse to extract variables section only
        try:
            with open(path, "rb") as f:
                temp_data = tomllib.load(f)

            if "variables" in temp_data:
                variables_section = temp_data["variables"]
                # Parse variable definitions
                for var_name, var_config in variables_section.items():
                    if isinstance(var_config, dict):
                        variable_definitions[var_name] = (
                            VariableDefinition.model_validate(var_config)
                        )
                    else:
                        # Simple default value
                        variable_definitions[var_name] = VariableDefinition(
                            default=var_config
                        )

                # Process variables if we have a variable manager
                if self.variable_manager:
                    # Get defaults from definitions
                    defaults = {}
                    for name, definition in variable_definitions.items():
                        if definition.default is not None:
                            defaults[name] = definition.default

                    # Merge provided variables with defaults
                    final_variables = self.variable_manager.merge_variables(
                        cli_vars=variables, defaults=defaults
                    )

                    # Validate variables
                    self.variable_manager.validate_variables(
                        final_variables, variable_definitions
                    )

                    # Check for missing required variables
                    missing = self.variable_manager.get_missing_required(
                        variable_definitions, final_variables
                    )
                    if missing:
                        # Try to prompt for missing variables
                        prompted = self.variable_manager.prompt_for_missing_variables(
                            missing, variable_definitions
                        )
                        final_variables.update(prompted)

                        # Re-validate after prompting
                        self.variable_manager.validate_variables(
                            final_variables, variable_definitions
                        )

        except (VariableValidationError, ConfigurationError):
            # Re-raise variable-related errors
            raise
        except Exception:
            # If we can't parse for variables, continue without them
            pass

        # Apply templating to the raw content if we have variables
        # But protect 'when' clauses from substitution (they should be evaluated at runtime)
        if self.variable_manager and final_variables:
            try:
                processed_content = self._substitute_variables_preserve_when(
                    raw_content, final_variables
                )
            except Exception as e:
                raise ValueError(f"Template processing failed: {e}")
        else:
            processed_content = raw_content

        # Now parse the processed content
        try:
            data = tomllib.loads(processed_content)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"TOML parsing failed after template processing: {e}")

        # Remove variables section from final data
        if "variables" in data:
            data.pop("variables")

        # Extract runbook metadata
        if "runbook" not in data:
            raise ValueError("Missing required [runbook] section")

        metadata = data.pop("runbook")

        # Validate required fields
        required_fields = ["title", "description", "version", "author", "created_at"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field in [runbook]: {field}")

        # Create nodes with implicit dependency support
        nodes: Dict[str, Union[ManualNode, FunctionNode, CommandNode]] = {}

        # Track node declaration order for implicit dependencies
        node_ids_in_order = list(data.keys())

        for i, (node_id, node_data) in enumerate(data.items()):
            if "type" not in node_data:
                raise ValueError(f"Missing required field 'type' in node: {node_id}")

            # Set node ID and name
            node_data["id"] = node_id
            if "name" not in node_data:
                node_data["name"] = node_id

            # Handle implicit dependencies and special keywords
            if "depends_on" not in node_data:
                # Implicit linear dependency: depend on previous node
                if i > 0:
                    previous_node_id = node_ids_in_order[i - 1]
                    node_data["depends_on"] = [previous_node_id]
                else:
                    node_data["depends_on"] = []
            else:
                # Process special keywords and normalize depends_on
                depends_on = node_data["depends_on"]
                if isinstance(depends_on, str):
                    if depends_on == "^":
                        # Depend on previous node
                        if i > 0:
                            previous_node_id = node_ids_in_order[i - 1]
                            node_data["depends_on"] = [previous_node_id]
                        else:
                            node_data["depends_on"] = []
                    elif depends_on == "*":
                        # Depend on all previous nodes
                        node_data["depends_on"] = node_ids_in_order[:i]
                    else:
                        # Regular string dependency
                        node_data["depends_on"] = [depends_on] if depends_on else []
                elif isinstance(depends_on, list):
                    # Process list, handling special keywords within
                    processed_deps = []
                    for dep in depends_on:
                        if dep == "^":
                            if i > 0:
                                processed_deps.append(node_ids_in_order[i - 1])
                        elif dep == "*":
                            processed_deps.extend(node_ids_in_order[:i])
                        else:
                            processed_deps.append(dep)
                    node_data["depends_on"] = processed_deps

            # Process conditional dependencies if present
            if "depends_on" in node_data:
                depends_on = node_data["depends_on"]
                if isinstance(depends_on, list):
                    # Parse conditional dependencies
                    clean_depends_on, when_clause = parse_dependencies(depends_on)
                    node_data["depends_on"] = clean_depends_on

                    # If there are conditional clauses and no explicit 'when', set it
                    if when_clause != "true" and "when" not in node_data:
                        node_data["when"] = when_clause
                    elif "when" in node_data and when_clause != "true":
                        # Combine existing 'when' with conditional dependencies using AND
                        existing_when = node_data["when"]
                        # Strip template markers for combination
                        existing_condition = existing_when.strip("{}").strip()
                        new_condition = when_clause.strip("{}").strip()
                        node_data["when"] = (
                            f"{{{{ ({existing_condition}) and ({new_condition}) }}}}"
                        )

            # Create appropriate node type
            node_type = node_data["type"]

            try:
                if node_type == NodeType.MANUAL.value:
                    nodes[node_id] = ManualNode.model_validate(node_data)
                elif node_type == NodeType.FUNCTION.value:
                    nodes[node_id] = FunctionNode.model_validate(node_data)
                elif node_type == NodeType.COMMAND.value:
                    nodes[node_id] = CommandNode.model_validate(node_data)
                else:
                    raise ValueError(f"Unknown node type: {node_type}")
            except ValidationError as e:
                # Convert Pydantic validation errors to user-friendly messages
                error_messages = []
                for error in e.errors():
                    if error["type"] == "extra_forbidden":
                        field = error["loc"][0]
                        error_messages.append(
                            f"Undefined field '{field}' for node type '{node_type}'"
                        )
                    else:
                        error_messages.append(
                            f"{error['msg']} at {'.'.join(str(loc) for loc in error['loc'])}"
                        )

                raise ValueError(
                    f"Error validating node '{node_id}': {'; '.join(error_messages)}"
                )

        # Validate critical nodes
        for node_id, node in nodes.items():
            if node.critical and node.skip:
                raise ValueError(
                    f"Skipping critical node not allowed: {node_id}: {node.skip}"
                )

        return Runbook(
            title=metadata["title"],
            description=metadata["description"],
            version=metadata["version"],
            author=metadata["author"],
            created_at=datetime.fromisoformat(metadata["created_at"]),
            nodes=nodes,
        )

    def get_variable_definitions(self, file_path: str) -> Dict[str, VariableDefinition]:
        """Extract variable definitions from a runbook file without full parsing.

        Args:
            file_path: Path to the runbook file

        Returns:
            Dictionary of variable definitions

        Raises:
            FileNotFoundError: If runbook file doesn't exist
            ValueError: If file format is invalid
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Runbook file not found: {file_path}")

        if not str(path).endswith(".playbook.toml"):
            raise ValueError("Runbook file must have a .playbook.toml extension")

        with open(path, "rb") as f:
            data = tomllib.load(f)

        variable_definitions = {}
        if "variables" in data:
            variables_section = data["variables"]
            # Parse variable definitions
            for var_name, var_config in variables_section.items():
                if isinstance(var_config, dict):
                    variable_definitions[var_name] = VariableDefinition.model_validate(
                        var_config
                    )
                else:
                    # Simple default value
                    variable_definitions[var_name] = VariableDefinition(
                        default=var_config
                    )

        return variable_definitions

    def _substitute_variables_preserve_when(
        self, content: str, variables: Dict[str, Any]
    ) -> str:
        """Apply variable substitution while preserving 'when' clauses.

        This method protects 'when' field values from variable substitution
        so they can be evaluated at runtime with proper context.
        """
        # Find all 'when' lines and temporarily replace them with placeholders
        when_pattern = r"^(\s*when\s*=\s*)(.*?)$"
        when_clauses = []
        placeholder_content = content

        def replace_when(match):
            when_clauses.append(match.group(2))  # Store the when clause value
            placeholder_index = len(when_clauses) - 1
            return f"{match.group(1)}__WHEN_PLACEHOLDER_{placeholder_index}__"

        # Replace when clauses with placeholders
        placeholder_content = re.sub(
            when_pattern, replace_when, content, flags=re.MULTILINE
        )

        # Apply variable substitution to the content with placeholders
        substituted_content = self.variable_manager.substitute_in_string(
            placeholder_content, variables
        )

        # Restore the original when clauses
        for i, when_clause in enumerate(when_clauses):
            placeholder = f"__WHEN_PLACEHOLDER_{i}__"
            substituted_content = substituted_content.replace(placeholder, when_clause)

        return substituted_content

    def save(self, runbook: Runbook, file_path: str) -> None:
        """Save a runbook to file (for create command)"""
        # Implementation for saving runbooks would go here
        # This would convert the Runbook model back to TOML format
        pass
