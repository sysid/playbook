# src/playbook/infrastructure/parser.py
import logging
import tomllib  # Use tomllib instead of tomli
from datetime import datetime
from pathlib import Path
from typing import Dict, Union

from ..domain.models import Runbook, NodeType, ManualNode, FunctionNode, CommandNode

logger = logging.getLogger(__name__)


class RunbookParser:
    """Parser for runbook TOML files"""

    def parse(self, file_path: str) -> Runbook:
        """Parse a runbook file"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Runbook file not found: {file_path}")

        if not str(path).endswith(".playbook.toml"):
            raise ValueError("Runbook file must have a .playbook.toml extension")

        with open(path, "rb") as f:
            data = tomllib.load(f)  # Use tomllib instead of tomli

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

            if node_type == NodeType.MANUAL.value:
                nodes[node_id] = ManualNode(**node_data)
            elif node_type == NodeType.FUNCTION.value:
                nodes[node_id] = FunctionNode(**node_data)
            elif node_type == NodeType.COMMAND.value:
                nodes[node_id] = CommandNode(**node_data)
            else:
                raise ValueError(f"Unknown node type: {node_type}")

        return Runbook(
            title=metadata["title"],
            description=metadata["description"],
            version=metadata["version"],
            author=metadata["author"],
            created_at=datetime.fromisoformat(metadata["created_at"]),
            nodes=nodes,
        )

    def save(self, runbook: Runbook, file_path: str) -> None:
        """Save a runbook to file (for create command)"""
        # Implementation for saving runbooks would go here
        # This would convert the Runbook model back to TOML format
        pass
