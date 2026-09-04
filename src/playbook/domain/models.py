from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StepType(str, Enum):
    MANUAL = "manual"
    COMMAND = "command"
    FUNCTION = "function"


class NodeStatus(str, Enum):
    OK = "ok"
    NOK = "nok"
    SKIPPED = "skipped"
    DISABLED = "disabled"
    PENDING = "pending"
    RUNNING = "running"
    ABORTED = "aborted"


class RunStatus(str, Enum):
    OK = "ok"
    NOK = "nok"
    RUNNING = "running"
    ABORTED = "aborted"


class TriggerType(str, Enum):
    RUN = "run"
    RESUME = "resume"


class BaseStep(BaseModel):
    id: str
    type: StepType
    name: str | None = None
    instructions: str | None = None
    required: bool = True
    enabled: bool = True
    enabled_if: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value or not all(
            character.isalnum() or character in "_-" for character in value
        ):
            raise ValueError("step id must contain only letters, numbers, '_' or '-'")
        return value


class ManualStep(BaseStep):
    type: Literal[StepType.MANUAL] = StepType.MANUAL
    instructions: str
    prompt: str = "Done?"


class CommandStep(BaseStep):
    type: Literal[StepType.COMMAND] = StepType.COMMAND
    command: str
    interactive: bool = False
    timeout_seconds: int = Field(default=300, gt=0)
    verify: str | None = None


class FunctionStep(BaseStep):
    type: Literal[StepType.FUNCTION] = StepType.FUNCTION
    plugin: str
    function: str
    params: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    verify: str | None = None


Step = Annotated[
    ManualStep | CommandStep | FunctionStep,
    Field(discriminator="type"),
]


class VariableDefinition(BaseModel):
    default: Any | None = None
    required: bool = False
    type: Literal["string", "int", "float", "bool", "list"] = "string"
    choices: list[Any] | None = None
    description: str | None = None
    min: int | float | None = None
    max: int | float | None = None
    pattern: str | None = None
    secret: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: list[Any] | None, info: Any) -> list[Any] | None:
        if value is None or "type" not in info.data:
            return value
        variable_type = info.data["type"]
        if variable_type == "int" and any(
            not isinstance(choice, int) or isinstance(choice, bool) for choice in value
        ):
            invalid = next(
                choice
                for choice in value
                if not isinstance(choice, int) or isinstance(choice, bool)
            )
            raise ValueError(f"choice {invalid!r} is not an integer")
        if variable_type == "float" and any(
            not isinstance(choice, (int, float)) or isinstance(choice, bool)
            for choice in value
        ):
            raise ValueError("all choices must be numbers")
        if variable_type == "bool" and any(
            not isinstance(choice, bool) for choice in value
        ):
            raise ValueError("all choices must be booleans")
        return value

    @field_validator("min", "max")
    @classmethod
    def validate_min_max(
        cls, value: int | float | None, info: Any
    ) -> int | float | None:
        if value is not None and info.data.get("type") not in ("int", "float"):
            raise ValueError("min/max can only be used with int or float types")
        return value


class Runbook(BaseModel):
    schema_version: Literal[2] = 2
    id: str
    title: str
    description: str = ""
    version: str | None = None
    author: str | None = None
    steps: list[Step]
    variable_definitions: dict[str, VariableDefinition] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    source_path: str
    definition_hash: str

    @model_validator(mode="after")
    def validate_steps(self) -> Runbook:
        seen: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError(f"Duplicate step id '{step.id}'")
            seen.add(step.id)
            if step.enabled_if is None:
                continue
            definition = self.variable_definitions.get(step.enabled_if)
            if definition is None:
                raise ValueError(
                    f"Step '{step.id}' enabled_if references unknown variable "
                    f"'{step.enabled_if}'"
                )
            if definition.secret:
                raise ValueError(
                    f"Step '{step.id}' enabled_if cannot reference secret variable "
                    f"'{step.enabled_if}'"
                )
            if definition.type != "bool":
                raise ValueError(
                    f"Step '{step.id}' enabled_if must reference a bool variable"
                )
        return self


class NodeExecution(BaseModel):
    workflow_name: str
    run_id: int
    node_id: str
    attempt: int
    start_time: datetime
    end_time: datetime | None = None
    status: NodeStatus
    operator_decision: str | None = None
    result_text: str | None = None
    exit_code: int | None = None
    exception: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = None


class RunInfo(BaseModel):
    workflow_name: str
    run_id: int
    start_time: datetime
    end_time: datetime | None = None
    status: RunStatus
    nodes_ok: int = 0
    nodes_nok: int = 0
    nodes_skipped: int = 0
    trigger: TriggerType
    source_path: str
    definition_hash: str
    variables: dict[str, Any] = Field(default_factory=dict)


class WorkflowSummary(BaseModel):
    """One workflow's run history, condensed for the overview listing."""

    workflow_name: str
    run_count: int
    last_start_time: datetime
    last_status: RunStatus
