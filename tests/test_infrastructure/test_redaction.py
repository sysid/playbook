from unittest.mock import patch

from playbook.domain.models import VariableDefinition
from playbook.infrastructure.redaction import Redactor
from playbook.infrastructure.variables import VariableManager


def test_redact_whenTextContainsSecrets_thenReplacesEveryNonEmptyValue() -> None:
    redactor = Redactor(["secret-value", "", "other"])

    assert (
        redactor.redact("secret-value and other and secret-value")
        == "[REDACTED] and [REDACTED] and [REDACTED]"
    )


def test_prompt_whenVariableIsSecret_thenHidesInput() -> None:
    manager = VariableManager(interactive=True)
    definition = VariableDefinition(
        type="string",
        required=True,
        secret=True,
    )

    with patch(
        "playbook.infrastructure.variables.Prompt.ask",
        return_value="secret-value",
    ) as prompt:
        result = manager.prompt_for_missing_variables(
            ["API_KEY"],
            {"API_KEY": definition},
        )

    assert result == {"API_KEY": "secret-value"}
    prompt.assert_called_once_with("Enter value for API_KEY", password=True)
