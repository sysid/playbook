# src/playbook/infrastructure/conditions.py
"""Conditional execution support for workflow nodes."""

import re
from typing import Dict, List, Any, Optional, Tuple
from jinja2 import Environment, Template, BaseLoader
from ..domain.models import NodeExecution, NodeStatus


class ConditionalDependency:
    """Represents a conditional dependency like 'node_id:success' or 'node_id:failure'."""

    def __init__(self, node_id: str, condition: Optional[str] = None):
        self.node_id = node_id
        self.condition = condition  # None, 'success', 'failure'

    @classmethod
    def parse(cls, dependency: str) -> "ConditionalDependency":
        """Parse a dependency string into node_id and optional condition.

        Examples:
            'deploy' -> ConditionalDependency('deploy', None)
            'deploy:success' -> ConditionalDependency('deploy', 'success')
            'deploy:failure' -> ConditionalDependency('deploy', 'failure')
        """
        if ":" in dependency:
            node_id, condition = dependency.split(":", 1)
            if condition not in ["success", "failure"]:
                raise ValueError(
                    f"Invalid condition '{condition}'. Must be 'success' or 'failure'"
                )
            return cls(node_id, condition)
        else:
            return cls(dependency, None)

    def to_when_clause(self) -> str:
        """Convert conditional dependency to equivalent 'when' clause."""
        if self.condition is None:
            return "true"  # Unconditional dependency
        elif self.condition == "success":
            return f'{{{{ has_succeeded("{self.node_id}") }}}}'
        elif self.condition == "failure":
            return f'{{{{ has_failed("{self.node_id}") }}}}'
        else:
            raise ValueError(f"Unknown condition: {self.condition}")


class ConditionContext:
    """Provides context functions for evaluating 'when' conditions."""

    def __init__(self, executions: Dict[str, NodeExecution]):
        self.executions = executions

    def previous_node(self, node_id: str) -> Dict[str, Any]:
        """Get execution details for a previous node."""
        execution = self.executions.get(node_id)
        if execution is None:
            return {
                "exit_code": None,
                "status": None,
                "output": None,
                "stdout": None,
                "stderr": None,
                "exists": False,
            }

        return {
            "exit_code": execution.exit_code,
            "status": execution.status.value if execution.status else None,
            "output": execution.stdout or execution.result_text,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
            "result_text": execution.result_text,
            "exists": True,
        }

    def has_succeeded(self, node_id: str) -> bool:
        """Check if a node has succeeded."""
        execution = self.executions.get(node_id)
        return execution is not None and execution.status == NodeStatus.OK

    def has_failed(self, node_id: str) -> bool:
        """Check if a node has failed."""
        execution = self.executions.get(node_id)
        return execution is not None and execution.status == NodeStatus.NOK

    def has_run(self, node_id: str) -> bool:
        """Check if a node has been executed (regardless of outcome)."""
        return node_id in self.executions

    def is_skipped(self, node_id: str) -> bool:
        """Check if a node was skipped."""
        execution = self.executions.get(node_id)
        return execution is not None and execution.status == NodeStatus.SKIPPED


class ConditionEvaluator:
    """Evaluates 'when' conditions using Jinja2 templates."""

    def __init__(self):
        self.env = Environment(loader=BaseLoader())

    def evaluate(
        self, condition: str, variables: Dict[str, Any], context: ConditionContext
    ) -> bool:
        """Evaluate a condition string and return boolean result.

        Args:
            condition: Jinja2 template string to evaluate
            variables: Workflow variables available in the condition
            context: Execution context with helper functions

        Returns:
            Boolean result of condition evaluation
        """
        try:
            # Create template from condition
            template = self.env.from_string(condition)

            # Prepare context with variables and helper functions
            template_context = {
                **variables,
                "previous_node": context.previous_node,
                "has_succeeded": context.has_succeeded,
                "has_failed": context.has_failed,
                "has_run": context.has_run,
                "is_skipped": context.is_skipped,
            }

            # Render template and convert to boolean
            result = template.render(template_context)

            # Handle different result types
            if isinstance(result, bool):
                return result
            elif isinstance(result, str):
                # Handle string boolean representations
                result_lower = result.lower().strip()
                if result_lower in ("true", "1", "yes", "on"):
                    return True
                elif result_lower in ("false", "0", "no", "off", ""):
                    return False
                else:
                    # Try to evaluate as Python expression for numbers/expressions
                    try:
                        return bool(eval(result_lower))
                    except:
                        # If all else fails, non-empty string is truthy
                        return bool(result_lower)
            else:
                # For numbers, None, etc.
                return bool(result)

        except Exception as e:
            raise ValueError(f"Failed to evaluate condition '{condition}': {e}")


def parse_dependencies(dependencies: List[str]) -> Tuple[List[str], str]:
    """Parse dependency list and return (node_ids, combined_when_clause).

    Converts conditional dependencies to equivalent 'when' conditions.

    Args:
        dependencies: List of dependency strings (may include conditions)

    Returns:
        Tuple of (clean_node_ids, when_clause)

    Examples:
        ['deploy'] -> (['deploy'], 'true')
        ['deploy:success'] -> (['deploy'], '{{ has_succeeded("deploy") }}')
        ['build', 'test:success'] -> (['build', 'test'], '{{ has_succeeded("test") }}')
    """
    node_ids = []
    conditions = []

    for dep in dependencies:
        conditional_dep = ConditionalDependency.parse(dep)
        node_ids.append(conditional_dep.node_id)

        if conditional_dep.condition:
            conditions.append(conditional_dep.to_when_clause())

    # Combine multiple conditions with AND
    if not conditions:
        when_clause = "true"
    elif len(conditions) == 1:
        when_clause = conditions[0]
    else:
        # Join multiple conditions with 'and'
        condition_parts = [c.strip("{}").strip() for c in conditions]
        when_clause = "{{ " + " and ".join(condition_parts) + " }}"

    return node_ids, when_clause
