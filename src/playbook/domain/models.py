# src/playbook/domain/models.py
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Literal, Any

from pydantic import BaseModel, Field, RootModel, field_validator


class NodeType(str, Enum):
    MANUAL = "Manual"
    FUNCTION = "Function"
    COMMAND = "Command"


class NodeStatus(str, Enum):
    OK = "ok"
    NOK = "nok"
    SKIPPED = "skipped"
    PENDING = "pending"
    RUNNING = "running"


class RunStatus(str, Enum):
    OK = "ok"
    NOK = "nok"
    RUNNING = "running"
    ABORTED = "aborted"


class TriggerType(str, Enum):
    RUN = "run"
    RESUME = "resume"


class BaseNode(BaseModel):
    id: str
    type: NodeType
    depends_on: List[str] = Field(default_factory=list)
    critical: bool = False
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_before: str = ""
    prompt_after: str = "Continue with the next step?"  # "" for no prompt
    skip: bool = False


class ManualNode(BaseNode):
    type: Literal[NodeType.MANUAL] = NodeType.MANUAL
    timeout: int = 300  # Default timeout in seconds

    model_config = {"extra": "forbid"}


class FunctionNode(BaseNode):
    type: Literal[NodeType.FUNCTION] = NodeType.FUNCTION
    # Plugin-based function execution
    plugin: str
    function: str  # Function name within plugin
    function_params: Dict[str, Any] = Field(default_factory=dict)
    # Plugin configuration overrides
    plugin_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class CommandNode(BaseNode):
    type: Literal[NodeType.COMMAND] = NodeType.COMMAND
    command_name: str
    interactive: bool = False
    timeout: int = 300  # Default timeout in seconds

    model_config = {"extra": "forbid"}


# Replace Node class with RootModel
class Node(RootModel):
    root: Union[ManualNode, FunctionNode, CommandNode]


class Runbook(BaseModel):
    title: str
    description: str
    version: str
    author: str
    created_at: datetime
    nodes: Dict[str, Union[ManualNode, FunctionNode, CommandNode]]


class NodeExecution(BaseModel):
    workflow_name: str
    run_id: int
    node_id: str
    attempt: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: NodeStatus
    operator_decision: Optional[str] = None
    result_text: Optional[str] = None
    exit_code: Optional[int] = None
    exception: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: Optional[int] = None


class RunInfo(BaseModel):
    workflow_name: str
    run_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: RunStatus
    nodes_ok: int = 0
    nodes_nok: int = 0
    nodes_skipped: int = 0
    trigger: TriggerType


class VariableDefinition(BaseModel):
    """Variable definition schema for workflow variables."""
    default: Optional[Any] = None
    required: bool = False
    type: Literal['string', 'int', 'float', 'bool', 'list'] = 'string'
    choices: Optional[List[Any]] = None
    description: Optional[str] = None
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None
    pattern: Optional[str] = None  # Regex pattern for strings

    @field_validator('choices')
    @classmethod
    def validate_choices(cls, v, info):
        """Ensure choices match the variable type."""
        if v is not None and 'type' in info.data:
            var_type = info.data['type']
            if var_type == 'int':
                for choice in v:
                    if not isinstance(choice, int):
                        raise ValueError(f"Choice '{choice}' is not an integer")
            elif var_type == 'float':
                for choice in v:
                    if not isinstance(choice, (int, float)):
                        raise ValueError(f"Choice '{choice}' is not a number")
            elif var_type == 'bool':
                for choice in v:
                    if not isinstance(choice, bool):
                        raise ValueError(f"Choice '{choice}' is not a boolean")
        return v

    @field_validator('min', 'max')
    @classmethod
    def validate_min_max(cls, v, info):
        """Ensure min/max are only used with numeric types."""
        if v is not None and 'type' in info.data:
            var_type = info.data['type']
            if var_type not in ['int', 'float']:
                raise ValueError("min/max can only be used with int or float types")
        return v
