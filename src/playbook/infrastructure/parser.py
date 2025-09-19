# src/playbook/infrastructure/parser.py
import logging
import tomllib  # Use tomllib instead of tomli
from datetime import datetime
from pathlib import Path
from typing import Dict, Union, Optional, Any

from pydantic import ValidationError

from ..domain.models import Runbook, NodeType, ManualNode, FunctionNode, CommandNode, VariableDefinition
from .variables import VariableManager, VariableValidationError
from ..domain.exceptions import ConfigurationError

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
        self,
        file_path: str,
        variables: Optional[Dict[str, Any]] = None
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
                        variable_definitions[var_name] = VariableDefinition.model_validate(var_config)
                    else:
                        # Simple default value
                        variable_definitions[var_name] = VariableDefinition(default=var_config)

                # Process variables if we have a variable manager
                if self.variable_manager:
                    # Get defaults from definitions
                    defaults = {}
                    for name, definition in variable_definitions.items():
                        if definition.default is not None:
                            defaults[name] = definition.default

                    # Merge provided variables with defaults
                    final_variables = self.variable_manager.merge_variables(
                        cli_vars=variables,
                        defaults=defaults
                    )

                    # Validate variables
                    self.variable_manager.validate_variables(final_variables, variable_definitions)

                    # Check for missing required variables
                    missing = self.variable_manager.get_missing_required(variable_definitions, final_variables)
                    if missing:
                        # Try to prompt for missing variables
                        prompted = self.variable_manager.prompt_for_missing_variables(missing, variable_definitions)
                        final_variables.update(prompted)

                        # Re-validate after prompting
                        self.variable_manager.validate_variables(final_variables, variable_definitions)

        except (VariableValidationError, ConfigurationError):
            # Re-raise variable-related errors
            raise
        except Exception:
            # If we can't parse for variables, continue without them
            pass

        # Apply templating to the raw content if we have variables
        if self.variable_manager and final_variables:
            try:
                processed_content = self.variable_manager.substitute_in_string(raw_content, final_variables)
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

        # Create nodes
        nodes: Dict[str, Union[ManualNode, FunctionNode, CommandNode]] = {}
        for node_id, node in nodes.items():
            if node.critical and node.skip:
                raise ValueError(
                    f"Skipping critical node not allowed: {node_id}: {node.skip}"
                )

        for node_id, node_data in data.items():
            if "type" not in node_data:
                raise ValueError(f"Missing required field 'type' in node: {node_id}")

            # Set node ID and name
            node_data["id"] = node_id
            if "name" not in node_data:
                node_data["name"] = node_id

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
                    variable_definitions[var_name] = VariableDefinition.model_validate(var_config)
                else:
                    # Simple default value
                    variable_definitions[var_name] = VariableDefinition(default=var_config)

        return variable_definitions

    def save(self, runbook: Runbook, file_path: str) -> None:
        """Save a runbook to file (for create command)"""
        # Implementation for saving runbooks would go here
        # This would convert the Runbook model back to TOML format
        pass
