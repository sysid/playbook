# src/playbook/domain/models.py
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field, RootModel  # Add RootModel import


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
    timeout: int = 300  # Default timeout in seconds
    prompt_before: str = ""
    prompt_after: str = "Continue with the next step?"
    skip: bool = False


class ManualNode(BaseNode):
    type: Literal[NodeType.MANUAL] = NodeType.MANUAL


class FunctionNode(BaseNode):
    type: Literal[NodeType.FUNCTION] = NodeType.FUNCTION
    function_name: str
    function_params: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict
    )


class CommandNode(BaseNode):
    type: Literal[NodeType.COMMAND] = NodeType.COMMAND
    command_name: str
    interactive: bool = False


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
