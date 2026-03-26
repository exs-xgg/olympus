"""Pydantic schemas for API request/response types."""

from datetime import datetime
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


# --- Task Schemas ---

TaskStatusType = Literal["queued", "running", "waiting_for_human", "completed", "failed"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    status: TaskStatusType
    assigned_agent: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    human_input_request: Optional[str] = None
    human_input_response: Optional[str] = None
    thread_id: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HITLApprovalDecision(BaseModel):
    action_id: str = Field(..., min_length=1, max_length=200)
    decision: Literal["approve", "edit", "reject"]
    params: dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = Field(default=None, max_length=2000)
    approved_by: Optional[str] = Field(default=None, max_length=200)


class TaskResumeRequest(BaseModel):
    human_input: str = Field(default="")
    approval: Optional[HITLApprovalDecision] = None


class TaskRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


# --- Agent Schemas ---

class AgentStatus(BaseModel):
    name: str
    role: str
    status: Literal["idle", "busy", "error"]
    capabilities: list[str]
    tools: list[str]
    current_task_id: Optional[str] = None
    model: str = "gpt-5-mini"
    uptime_seconds: int = 0
    tokens_used: int = 0
    error_count: int = 0
    tasks_done: int = 0
    temperature: float = 0.2
    max_tokens: int = 4096


class AgentProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: str = Field(..., min_length=1, max_length=300)
    system_prompt: str = Field(..., min_length=1, max_length=12000)
    model: str = Field(default="gpt-5-mini", min_length=1, max_length=120)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    tools: list[str] = Field(default_factory=list)


class AgentProfileResponse(BaseModel):
    id: str
    name: str
    role: str
    system_prompt: str
    model: str
    temperature: float
    tools: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Chat Schemas ---

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    agent_name: str = Field(..., min_length=1, max_length=200)
    thread_id: Optional[str] = Field(default=None, max_length=200)


class AgentChatResponse(BaseModel):
    thread_id: str
    agent_name: str
    response: str


class AgentChatMessageResponse(BaseModel):
    thread_id: str
    role: Literal["user", "agent", "system"]
    content: str
    agent_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Log Schemas ---

class ActionLogResponse(BaseModel):
    id: str
    task_id: str
    agent_name: Optional[str] = None
    action: str
    detail: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- WebSocket Event Schemas ---

class WSEvent(BaseModel):
    type: Literal["task_update", "agent_update", "log", "hitl_request"]
    data: dict


# --- MCP Schemas ---

class MCPEnvVar(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(default="", max_length=4000)


class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    transport: Literal["stdio", "sse", "http"] = "stdio"
    command: str = Field(..., min_length=1, max_length=500)
    args: str = Field(default="", max_length=2000)
    env: list[MCPEnvVar] = Field(default_factory=list)


class MCPServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    command: str
    args: str
    env_keys: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Audit Schemas ---

class InterventionAuditResponse(BaseModel):
    id: str
    task_id: str
    action: str
    detail: Optional[str] = None
    timestamp: datetime
    agent_name: Optional[str] = None
