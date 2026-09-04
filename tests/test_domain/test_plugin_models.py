"""Tests for plugin-backed function steps."""

import pytest
from pydantic import ValidationError

from playbook.domain.models import FunctionStep, StepType


def test_function_step_contains_plugin_configuration():
    step = FunctionStep(
        id="notify",
        plugin="slack",
        function="send_message",
        params={"channel": "#test", "message": "Hello"},
        config={"webhook_url": "https://example.invalid"},
    )

    assert step.params == {"channel": "#test", "message": "Hello"}
    assert step.config == {"webhook_url": "https://example.invalid"}
    assert step.type == StepType.FUNCTION


@pytest.mark.parametrize(
    "values",
    [
        {"function": "send_message"},
        {"plugin": "slack"},
        {},
    ],
)
def test_function_step_requires_plugin_and_function(values):
    with pytest.raises(ValidationError):
        FunctionStep(id="notify", **values)


def test_function_step_defaults_to_empty_parameters_and_configuration():
    step = FunctionStep(id="notify", plugin="python", function="notify")

    assert step.params == {}
    assert step.config == {}
