"""Agent domain – request / response schemas."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class AgentStatus(str, Enum):
    idle = "idle"
    busy = "busy"
    offline = "offline"
    degraded = "degraded"


class AgentRegisterRequest(BaseModel):
    agent_name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)
    callback_url: HttpUrl | None = None
    mode: str = Field(default="polling", pattern="^(polling|callback)$")
    skills: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    concurrency: int = Field(default=1, ge=1, le=50)
    pricing: dict[str, int] = Field(default_factory=dict)
    region: str = Field(default="global", max_length=50)
    tooling: list[str] = Field(default_factory=list)
    compliance_flags: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentPublicProfile(BaseModel):
    agent_id: str
    agent_name: str
    description: str
    callback_url: HttpUrl | None
    mode: str
    skills: list[str]
    categories: list[str]
    concurrency: int
    pricing: dict[str, int]
    region: str
    tooling: list[str]
    compliance_flags: dict[str, Any]
    metadata: dict[str, Any]


class AgentTaskSummary(BaseModel):
    task_id: str
    title: str
    category: str
    status: str
    progress: int
    reward: int
    currency: str
    owner_username: str | None = None


class AgentBidSummary(BaseModel):
    proposal_id: str
    task_id: str
    task_title: str
    proposal_status: str
    estimated_total_minutes: int
    created_at: str


class AgentHomepageSummary(BaseModel):
    completed_task_count: int = 0
    bidding_task_count: int = 0
    pending_execution_count: int = 0
    running_task_count: int = 0
    awaiting_acceptance_count: int = 0


class AgentHomepageResponse(BaseModel):
    agent_id: str
    agent_name: str
    description: str
    status: str
    healthy: bool
    current_load: int
    max_load: int
    last_heartbeat_at: str | None = None
    balance: int
    profile_url: str
    profile: AgentPublicProfile
    summary: AgentHomepageSummary
    completed_tasks: list[AgentTaskSummary] = Field(default_factory=list)
    bidding_tasks: list[AgentBidSummary] = Field(default_factory=list)
    pending_execution_tasks: list[AgentTaskSummary] = Field(default_factory=list)
    running_tasks: list[AgentTaskSummary] = Field(default_factory=list)
    awaiting_acceptance_tasks: list[AgentTaskSummary] = Field(default_factory=list)


class AgentRegisterResponse(BaseModel):
    agent: dict[str, str]


class HeartbeatRequest(BaseModel):
    status: AgentStatus
    current_load: int = Field(ge=0, le=1000)
    max_load: int = Field(ge=1, le=1000)
    healthy: bool = True
