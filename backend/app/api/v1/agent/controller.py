"""Agent HTTP endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ....config import BASE_URL, FRONTEND_BASE_URL, HEARTBEAT_TIMEOUT_SECONDS
from ....database import get_store
from ....common.deps import get_current_agent
from ..matching.schema import LedgerEntry, LedgerResponse
from .schema import (
    AgentBidSummary,
    AgentHomepageResponse,
    AgentHomepageSummary,
    AgentPublicProfile,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentTaskSummary,
    HeartbeatRequest,
)
from . import service

router = APIRouter(prefix="/agents", tags=["Agent"])


@router.post("/register", response_model=AgentRegisterResponse)
def register_agent(payload: AgentRegisterRequest) -> AgentRegisterResponse:
    agent = service.register(payload)
    return AgentRegisterResponse(
        agent={
            "agent_id": agent.agent_id,
            "username": payload.agent_name,
            "api_key": agent.api_key,
            "verification_code": agent.verification_code,
            "profile_url": f"{FRONTEND_BASE_URL}/agent/{payload.agent_name}",
        }
    )


@router.get("/me", response_model=AgentPublicProfile)
def get_me(agent=Depends(get_current_agent)) -> AgentPublicProfile:
    reg = agent.registration
    return AgentPublicProfile(
        agent_id=agent.agent_id,
        agent_name=reg.agent_name,
        description=reg.description,
        callback_url=reg.callback_url,
        mode=reg.mode,
        skills=reg.skills,
        categories=reg.categories,
        concurrency=reg.concurrency,
        pricing=reg.pricing,
        region=reg.region,
        tooling=reg.tooling,
        compliance_flags=reg.compliance_flags,
        metadata=reg.metadata,
    )


@router.get("/public/{agent_name}", response_model=AgentHomepageResponse)
def get_public_agent_homepage(agent_name: str) -> AgentHomepageResponse:
    store = get_store()
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agent = store.find_agent_by_name(agent_name)
    if not agent:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    reg = agent.registration
    profile = AgentPublicProfile(
        agent_id=agent.agent_id,
        agent_name=reg.agent_name,
        description=reg.description,
        callback_url=reg.callback_url,
        mode=reg.mode,
        skills=reg.skills,
        categories=reg.categories,
        concurrency=reg.concurrency,
        pricing=reg.pricing,
        region=reg.region,
        tooling=reg.tooling,
        compliance_flags=reg.compliance_flags,
        metadata=reg.metadata,
    )

    def task_summary(task) -> AgentTaskSummary:
        return AgentTaskSummary(
            task_id=task.task_id,
            title=task.title,
            category=task.category,
            status=task.status.value,
            progress=task.progress,
            reward=task.reward,
            currency=task.currency,
            owner_username=task.owner_username,
        )

    completed_tasks = [
        task_summary(t)
        for t in store.tasks.values()
        if t.assigned_agent_id == agent.agent_id and t.status.value == "completed"
    ]
    pending_execution_tasks = [
        task_summary(t)
        for t in store.tasks.values()
        if t.assigned_agent_id == agent.agent_id and t.status.value == "assigned" and (t.progress or 0) == 0
    ]
    running_tasks = [
        task_summary(t)
        for t in store.tasks.values()
        if t.assigned_agent_id == agent.agent_id and t.status.value == "assigned" and 0 < (t.progress or 0) < 100
    ]
    awaiting_acceptance_tasks = [
        task_summary(t)
        for t in store.tasks.values()
        if t.assigned_agent_id == agent.agent_id and t.status.value in {"submitted", "verified"}
    ]
    bidding_tasks = []
    for proposal in store.proposals.values():
        if proposal.agent_id != agent.agent_id or proposal.status.value != "pending":
            continue
        task = store.get_task(proposal.task_id)
        bidding_tasks.append(
            AgentBidSummary(
                proposal_id=proposal.proposal_id,
                task_id=proposal.task_id,
                task_title=task.title if task else proposal.task_id,
                proposal_status=proposal.status.value,
                estimated_total_minutes=proposal.estimated_total_minutes,
                created_at=proposal.created_at,
            )
        )

    return AgentHomepageResponse(
        agent_id=agent.agent_id,
        agent_name=agent.registration.agent_name,
        description=agent.registration.description,
        status=agent.status.value,
        healthy=agent.healthy,
        current_load=agent.current_load,
        max_load=agent.max_load,
        last_heartbeat_at=agent.last_heartbeat_at,
        balance=agent.balance,
        profile_url=f"{FRONTEND_BASE_URL}/agent/{agent.registration.agent_name}",
        profile=profile,
        summary=AgentHomepageSummary(
            completed_task_count=len(completed_tasks),
            bidding_task_count=len(bidding_tasks),
            pending_execution_count=len(pending_execution_tasks),
            running_task_count=len(running_tasks),
            awaiting_acceptance_count=len(awaiting_acceptance_tasks),
        ),
        completed_tasks=completed_tasks,
        bidding_tasks=bidding_tasks,
        pending_execution_tasks=pending_execution_tasks,
        running_tasks=running_tasks,
        awaiting_acceptance_tasks=awaiting_acceptance_tasks,
    )


@router.post("/heartbeat", response_class=JSONResponse)
def heartbeat(payload: HeartbeatRequest, agent=Depends(get_current_agent)):
    print(f"[castor] heartbeat: {json.dumps(payload.model_dump(), ensure_ascii=False)}")
    agent = service.heartbeat(agent, payload)
    return {
        "success": True,
        "agent_id": agent.agent_id,
        "status": agent.status,
        "current_load": agent.current_load,
        "last_heartbeat_at": agent.last_heartbeat_at,
    }


@router.get("/ledger/me", response_model=LedgerResponse)
def get_ledger(agent=Depends(get_current_agent)) -> LedgerResponse:
    store = get_store()
    entries = store.ledger_for_agent(agent.agent_id)
    return LedgerResponse(balance=agent.balance, entries=entries)
