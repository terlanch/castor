"""Task domain – request / response schemas."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    queued = "queued"
    assigned = "assigned"
    submitted = "submitted"
    verified = "verified"
    completed = "completed"
    rejected = "rejected"


class SettlementState(str, Enum):
    pending_verification = "pending_verification"
    verified = "verified"
    rejected = "rejected"
    credited = "credited"
    disputed = "disputed"


class PaymentState(str, Enum):
    reserved = "reserved"
    awaiting_user_acceptance = "awaiting_user_acceptance"
    paid = "paid"
    refunded = "refunded"


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
    schema: dict[str, Any] = Field(default_factory=dict)  # noqa: shadows parent
    examples: list[dict[str, Any] | str] = Field(default_factory=list)


class ProposalStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class PlanStep(BaseModel):
    step_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    estimated_minutes: int = Field(default=30, ge=1)
    status: str = Field(default="pending")  # pending | in_progress | completed | skipped


class ExecutionPlan(BaseModel):
    summary: str = Field(min_length=2, max_length=500)
    steps: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    estimated_cost: int | None = Field(default=None, ge=0)


class TaskProposal(BaseModel):
    proposal_id: str
    task_id: str
    agent_id: str
    agent_name: str
    plan_steps: list[PlanStep] = Field(default_factory=list)
    estimated_total_minutes: int = Field(default=60, ge=1)
    message: str = Field(default="", max_length=2000)
    status: ProposalStatus = ProposalStatus.pending
    created_at: str = ""
    accepted_at: str | None = None


class UploadedFile(BaseModel):
    """Metadata for a file uploaded by an Agent."""
    file_id: str
    task_id: str
    agent_id: str
    original_filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    download_url: str = ""
    uploaded_at: str = ""


class SubmissionProof(BaseModel):
    trace_id: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    file_ids: list[str] = Field(default_factory=list)
    tool_usage: list[str] = Field(default_factory=list)


class SubmissionStats(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class TaskSubmission(BaseModel):
    output: dict[str, Any]
    proof: SubmissionProof = Field(default_factory=SubmissionProof)
    stats: SubmissionStats = Field(default_factory=SubmissionStats)
    submitted_at: str | None = None
    submitted_by_agent_id: str | None = None


# ── Full task payload ──────────────────────────────────────────────────

class TaskPayload(BaseModel):
    task_id: str
    category: str
    title: str
    owner_user_id: str | None = None
    owner_username: str | None = None
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
    rejected_agent_ids: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.queued
    progress: int = Field(default=0, ge=0, le=100)
    settlement_state: SettlementState | None = None
    payment_state: PaymentState | None = None
    verification_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    skills_required: list[str] = Field(default_factory=list)
    task_region: str = Field(default="global")
    submission: TaskSubmission | None = None
    execution_plan: ExecutionPlan | None = None


# ── Requests ───────────────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    category: str = "general"
    title: str = ""
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


class PollTasksRequest(BaseModel):
    categories: list[str] = Field(default_factory=list)
    max_tasks: int = Field(default=1, ge=1, le=10)


class AcceptTaskRequest(BaseModel):
    execution_plan: ExecutionPlan | None = None


class RejectTaskRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=200)


class SubmitProposalRequest(BaseModel):
    """Agent submits a structured execution plan to compete for a task."""
    plan_steps: list[PlanStep] = Field(min_length=1)
    estimated_total_minutes: int = Field(ge=1, le=100_000)
    message: str = Field(default="", max_length=2000)


class ProgressUpdateRequest(BaseModel):
    progress: int = Field(ge=0, le=100)
    message: str = Field(min_length=1, max_length=500)


class StepProgressRequest(BaseModel):
    """Agent reports progress on a specific step of the plan."""
    step_number: int = Field(ge=1)
    status: str = Field(pattern="^(in_progress|completed|skipped)$")
    message: str = Field(default="", max_length=500)


class SubmitTaskRequest(BaseModel):
    output: dict[str, Any]
    proof: SubmissionProof = Field(default_factory=SubmissionProof)
    stats: SubmissionStats = Field(default_factory=SubmissionStats)


class VerifyTaskRequest(BaseModel):
    note: str = Field(default="Approved by admin.", min_length=2, max_length=500)


class RejectSubmissionRequest(BaseModel):
    note: str = Field(default="Rejected by admin.", min_length=2, max_length=500)
