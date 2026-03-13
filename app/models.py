from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class AgentStatus(str, Enum):
    idle = "idle"
    busy = "busy"
    offline = "offline"
    degraded = "degraded"


class TaskStatus(str, Enum):
    queued = "queued"
    assigned = "assigned"
    completed = "completed"
    rejected = "rejected"


class SettlementState(str, Enum):
    pending_verification = "pending_verification"
    verified = "verified"
    rejected = "rejected"
    credited = "credited"
    disputed = "disputed"


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


class AgentRegisterResponse(BaseModel):
    agent: dict[str, str]


class HeartbeatRequest(BaseModel):
    status: AgentStatus
    current_load: int = Field(ge=0, le=1000)
    max_load: int = Field(ge=1, le=1000)
    healthy: bool = True


class PollTasksRequest(BaseModel):
    categories: list[str] = Field(default_factory=list)
    max_tasks: int = Field(default=1, ge=1, le=10)


class VerificationRule(BaseModel):
    type: str = "schema_plus_sampling"
    min_items: int | None = None


class RetryPolicy(BaseModel):
    max_retries: int = 1


class ComplianceRule(BaseModel):
    restricted_domains: list[str] = Field(default_factory=list)
    requires_manual_review: bool = False


class DeliverableSpec(BaseModel):
    format: str = "json"
    description: str | None = None
    schema: dict[str, Any] = Field(default_factory=dict)
    examples: list[dict[str, Any] | str] = Field(default_factory=list)


class TaskPayload(BaseModel):
    task_id: str
    category: str
    title: str
    goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    deliverable: DeliverableSpec = Field(default_factory=DeliverableSpec)
    acceptance_criteria: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    reward: int = Field(ge=1)
    currency: str = "CASTOR_CREDIT"
    priority: str = "normal"
    sla_seconds: int = Field(default=1800, ge=60)
    verification_rule: VerificationRule = Field(default_factory=VerificationRule)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    compliance: ComplianceRule = Field(default_factory=ComplianceRule)
    assigned_agent_id: str | None = None
    status: TaskStatus = TaskStatus.queued
    progress: int = Field(default=0, ge=0, le=100)


class CreateTaskRequest(BaseModel):
    category: str
    title: str
    goal: str | None = None
    constraints: list[str] = Field(default_factory=list)
    deliverable: DeliverableSpec = Field(default_factory=DeliverableSpec)
    acceptance_criteria: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    reward: int = Field(ge=1)
    currency: str = "CASTOR_CREDIT"
    priority: str = "normal"
    sla_seconds: int = Field(default=1800, ge=60)
    verification_rule: VerificationRule = Field(default_factory=VerificationRule)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    compliance: ComplianceRule = Field(default_factory=ComplianceRule)


class RejectTaskRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=200)


class ProgressUpdateRequest(BaseModel):
    progress: int = Field(ge=0, le=100)
    message: str = Field(min_length=1, max_length=500)


class SubmissionProof(BaseModel):
    trace_id: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    tool_usage: list[str] = Field(default_factory=list)


class SubmissionStats(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class SubmitTaskRequest(BaseModel):
    output: dict[str, Any]
    proof: SubmissionProof = Field(default_factory=SubmissionProof)
    stats: SubmissionStats = Field(default_factory=SubmissionStats)


class LedgerEntry(BaseModel):
    entry_id: str
    agent_id: str
    task_id: str
    amount: int
    currency: str = "CASTOR_CREDIT"
    settlement_state: SettlementState
    note: str


class LedgerResponse(BaseModel):
    balance: int
    currency: str = "CASTOR_CREDIT"
    entries: list[LedgerEntry]
