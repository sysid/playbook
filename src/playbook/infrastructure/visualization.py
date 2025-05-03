# src/playbook/infrastructure/visualization.py
from typing import Dict

import graphviz

from ..domain.models import NodeType, Runbook
from ..domain.ports import Visualizer


class GraphvizVisualizer(Visualizer):
    """Graphviz visualization adapter"""

    def export_dot(self, runbook: Runbook, output_path: str) -> None:
        """Export runbook as DOT file"""
        # Create a new directed graph
        dot = graphviz.Digraph(
            name=runbook.title,
            comment=runbook.description,
            format="dot"
        )

        # Add each node to the graph
        for node_id, node in runbook.nodes.items():
            # Set node attributes based on type
            attrs = self._get_node_attributes(node.type, node.critical)

            # Use name if provided, otherwise node_id
            label = node.name if node.name else node_id

            dot.node(node_id, label, **attrs)

        # Add edges for dependencies
        for node_id, node in runbook.nodes.items():
            for dep_id in node.depends_on:
                dot.edge(dep_id, node_id)

            # Save to file
            dot.save(output_path)

    def _get_node_attributes(self, node_type: NodeType, critical: bool) -> Dict[str, str]:
        """Get node visualization attributes based on type"""
        attrs = {}

        # Shape and fill based on node type
        if node_type == NodeType.MANUAL:
            attrs["shape"] = "ellipse"
            attrs["style"] = "filled"
            attrs["fillcolor"] = "lightblue"
        elif node_type == NodeType.FUNCTION:
            attrs["shape"] = "box"
            attrs["style"] = "filled"
            attrs["fillcolor"] = "lightgreen"
        elif node_type == NodeType.COMMAND:
            attrs["shape"] = "hexagon"
            attrs["style"] = "filled"
            attrs["fillcolor"] = "lightyellow"

        # Add red border for critical nodes
        if critical:
            attrs["penwidth"] = "2"
            attrs["color"] = "red"

        return attrs
