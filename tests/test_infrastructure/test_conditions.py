# tests/test_infrastructure/test_conditions.py
"""Tests for conditional execution support."""

import pytest
from datetime import datetime
from typing import Dict

from src.playbook.infrastructure.conditions import (
    ConditionalDependency,
    ConditionContext,
    ConditionEvaluator,
    parse_dependencies,
)
from src.playbook.domain.models import NodeExecution, NodeStatus


class TestConditionalDependency:
    def test_parse_simple_dependency(self):
        """Test parsing simple dependency without condition."""
        dep = ConditionalDependency.parse("deploy")
        assert dep.node_id == "deploy"
        assert dep.condition is None

    def test_parse_success_condition(self):
        """Test parsing success condition dependency."""
        dep = ConditionalDependency.parse("deploy:success")
        assert dep.node_id == "deploy"
        assert dep.condition == "success"

    def test_parse_failure_condition(self):
        """Test parsing failure condition dependency."""
        dep = ConditionalDependency.parse("deploy:failure")
        assert dep.node_id == "deploy"
        assert dep.condition == "failure"

    def test_parse_invalid_condition(self):
        """Test parsing invalid condition raises error."""
        with pytest.raises(ValueError, match="Invalid condition 'unknown'"):
            ConditionalDependency.parse("deploy:unknown")

    def test_to_when_clause_simple(self):
        """Test converting simple dependency to when clause."""
        dep = ConditionalDependency("deploy", None)
        assert dep.to_when_clause() == "true"

    def test_to_when_clause_success(self):
        """Test converting success condition to when clause."""
        dep = ConditionalDependency("deploy", "success")
        assert dep.to_when_clause() == '{{ has_succeeded("deploy") }}'

    def test_to_when_clause_failure(self):
        """Test converting failure condition to when clause."""
        dep = ConditionalDependency("deploy", "failure")
        assert dep.to_when_clause() == '{{ has_failed("deploy") }}'


class TestConditionContext:
    def test_previous_node_exists(self):
        """Test accessing previous node that exists."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
            exit_code=0,
            stdout="Success",
        )

        context = ConditionContext({"deploy": execution})
        result = context.previous_node("deploy")

        assert result["exists"] is True
        assert result["exit_code"] == 0
        assert result["status"] == "ok"
        assert result["stdout"] == "Success"

    def test_previous_node_missing(self):
        """Test accessing previous node that doesn't exist."""
        context = ConditionContext({})
        result = context.previous_node("deploy")

        assert result["exists"] is False
        assert result["exit_code"] is None
        assert result["status"] is None

    def test_has_succeeded(self):
        """Test has_succeeded helper function."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )

        context = ConditionContext({"deploy": execution})
        assert context.has_succeeded("deploy") is True
        assert context.has_succeeded("missing") is False

    def test_has_failed(self):
        """Test has_failed helper function."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.NOK,
        )

        context = ConditionContext({"deploy": execution})
        assert context.has_failed("deploy") is True
        assert context.has_failed("missing") is False

    def test_has_run(self):
        """Test has_run helper function."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )

        context = ConditionContext({"deploy": execution})
        assert context.has_run("deploy") is True
        assert context.has_run("missing") is False

    def test_is_skipped(self):
        """Test is_skipped helper function."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="deploy",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.SKIPPED,
        )

        context = ConditionContext({"deploy": execution})
        assert context.is_skipped("deploy") is True
        assert context.is_skipped("missing") is False


class TestConditionEvaluator:
    def test_evaluate_true_condition(self):
        """Test evaluating true condition."""
        evaluator = ConditionEvaluator()
        context = ConditionContext({})

        result = evaluator.evaluate("true", {}, context)
        assert result is True

    def test_evaluate_false_condition(self):
        """Test evaluating false condition."""
        evaluator = ConditionEvaluator()
        context = ConditionContext({})

        result = evaluator.evaluate("false", {}, context)
        assert result is False

    def test_evaluate_variable_condition(self):
        """Test evaluating condition with variables."""
        evaluator = ConditionEvaluator()
        context = ConditionContext({})
        variables = {"ENVIRONMENT": "prod"}

        result = evaluator.evaluate("{{ ENVIRONMENT == 'prod' }}", variables, context)
        assert result is True

        result = evaluator.evaluate("{{ ENVIRONMENT == 'dev' }}", variables, context)
        assert result is False

    def test_evaluate_helper_function_condition(self):
        """Test evaluating condition with helper functions."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
        )

        evaluator = ConditionEvaluator()
        context = ConditionContext({"build": execution})

        result = evaluator.evaluate("{{ has_succeeded('build') }}", {}, context)
        assert result is True

        result = evaluator.evaluate("{{ has_failed('build') }}", {}, context)
        assert result is False

    def test_evaluate_complex_condition(self):
        """Test evaluating complex condition with multiple parts."""
        execution = NodeExecution(
            workflow_name="test",
            run_id=1,
            node_id="build",
            attempt=1,
            start_time=datetime.now(),
            status=NodeStatus.OK,
            exit_code=0,
        )

        evaluator = ConditionEvaluator()
        context = ConditionContext({"build": execution})
        variables = {"ENVIRONMENT": "prod"}

        condition = "{{ ENVIRONMENT == 'prod' and has_succeeded('build') and previous_node('build').exit_code == 0 }}"
        result = evaluator.evaluate(condition, variables, context)
        assert result is True

    def test_evaluate_invalid_condition(self):
        """Test evaluating invalid condition raises error."""
        evaluator = ConditionEvaluator()
        context = ConditionContext({})

        with pytest.raises(ValueError, match="Failed to evaluate condition"):
            evaluator.evaluate("{{ invalid_syntax", {}, context)


class TestParseDependencies:
    def test_parse_simple_dependencies(self):
        """Test parsing simple dependencies without conditions."""
        dependencies = ["build", "test"]
        node_ids, when_clause = parse_dependencies(dependencies)

        assert node_ids == ["build", "test"]
        assert when_clause == "true"

    def test_parse_conditional_dependencies(self):
        """Test parsing conditional dependencies."""
        dependencies = ["build:success", "test:failure"]
        node_ids, when_clause = parse_dependencies(dependencies)

        assert node_ids == ["build", "test"]
        assert 'has_succeeded("build")' in when_clause
        assert 'has_failed("test")' in when_clause
        assert "and" in when_clause

    def test_parse_mixed_dependencies(self):
        """Test parsing mixed simple and conditional dependencies."""
        dependencies = ["build", "test:success"]
        node_ids, when_clause = parse_dependencies(dependencies)

        assert node_ids == ["build", "test"]
        assert when_clause == '{{ has_succeeded("test") }}'

    def test_parse_single_conditional_dependency(self):
        """Test parsing single conditional dependency."""
        dependencies = ["deploy:success"]
        node_ids, when_clause = parse_dependencies(dependencies)

        assert node_ids == ["deploy"]
        assert when_clause == '{{ has_succeeded("deploy") }}'
