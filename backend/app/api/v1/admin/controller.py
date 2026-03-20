"""Admin HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ....config import HEARTBEAT_TIMEOUT_SECONDS
from ....database import get_store, utc_now
from ....common.deps import require_admin_token
from ..matching.service import build_candidates_for_task
from ..task.schema import (
    CreateTaskRequest,
    RejectSubmissionRequest,
    VerifyTaskRequest,
)
from ..task import service as task_service
from .service import build_agent_admin_payload, build_task_admin_payload

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/agents", response_class=JSONResponse)
def admin_agents(_=Depends(require_admin_token)):
    store = get_store()
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agents = [build_agent_admin_payload(a) for a in store.agents.values()]
    return {"total": len(agents), "agents": agents}


@router.get("/agents/{agent_id}", response_class=JSONResponse)
def admin_agent_detail(agent_id: str, _=Depends(require_admin_token)):
    store = get_store()
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agent = store.agents.get(agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    tasks = [t.model_dump() for t in store.tasks.values() if t.assigned_agent_id == agent_id]
    return {
        "agent": build_agent_admin_payload(agent),
        "tasks": tasks,
        "ledger": [e.model_dump() for e in store.ledger_for_agent(agent_id)],
    }


@router.get("/dashboard", response_class=JSONResponse)
def admin_dashboard(_=Depends(require_admin_token)):
    store = get_store()
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agents = list(store.agents.values())
    tasks = store.list_tasks()
    online = {"idle", "busy", "degraded"}
    total_credits = sum(e.amount for e in store.ledger_entries)
    return {
        "agents": {
            "total": len(agents),
            "online": sum(1 for a in agents if a.status.value in online),
            "idle": sum(1 for a in agents if a.status.value == "idle"),
            "busy": sum(1 for a in agents if a.status.value == "busy"),
            "degraded": sum(1 for a in agents if a.status.value == "degraded"),
        },
        "tasks": {
            "total": len(tasks),
            "queued": sum(1 for t in tasks if t.status.value == "queued"),
            "assigned": sum(1 for t in tasks if t.status.value == "assigned"),
            "submitted": sum(1 for t in tasks if t.status.value == "submitted"),
            "completed": sum(1 for t in tasks if t.status.value == "completed"),
            "rejected": sum(1 for t in tasks if t.status.value == "rejected"),
        },
        "ledger": {"total_entries": len(store.ledger_entries), "total_credited": total_credits, "currency": "CASTOR_CREDIT"},
        "server_time": utc_now(),
    }


@router.get("/tasks", response_class=JSONResponse)
def admin_tasks(_=Depends(require_admin_token)):
    store = get_store()
    return {"total": len(store.tasks), "tasks": [build_task_admin_payload(t) for t in store.list_tasks()]}


@router.get("/tasks/{task_id}", response_class=JSONResponse)
def admin_task_detail(task_id: str, _=Depends(require_admin_token)):
    task = get_store().get_task(task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return {"task": build_task_admin_payload(task)}


@router.get("/tasks/{task_id}/candidates", response_class=JSONResponse)
def admin_task_candidates(task_id: str, _=Depends(require_admin_token)):
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    candidates = store.candidate_pool.get(task_id, [])
    return {
        "task_id": task_id,
        "total": len(candidates),
        "candidates": sorted(
            [
                {
                    "agent_id": c.agent_id,
                    "agent_name": store.agents[c.agent_id].registration.agent_name if c.agent_id in store.agents else "unknown",
                    "score": c.score,
                    "matched_tags": c.matched_tags,
                    "reason": c.reason,
                }
                for c in candidates
            ],
            key=lambda x: x["score"],
            reverse=True,
        ),
    }


@router.get("/tasks/{task_id}/proposals", response_class=JSONResponse)
def admin_task_proposals(task_id: str, _=Depends(require_admin_token)):
    store = get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    proposals = store.list_proposals_for_task(task_id)
    return {
        "task_id": task_id,
        "total": len(proposals),
        "proposals": [p.model_dump(mode="json") for p in proposals],
    }


@router.post("/tasks", response_class=JSONResponse)
def create_task(payload: CreateTaskRequest, _=Depends(require_admin_token)):
    task = task_service.create_task(payload)
    return {"success": True, "task": task.model_dump()}


@router.post("/tasks/{task_id}/verify", response_class=JSONResponse)
def verify_task(task_id: str, payload: VerifyTaskRequest, _=Depends(require_admin_token)):
    task = get_store().verify_task(task_id, payload.note)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not awaiting verification.")
    return {"success": True, "task": task.model_dump(mode="json")}


@router.post("/tasks/{task_id}/reject-submission", response_class=JSONResponse)
def reject_submission(task_id: str, payload: RejectSubmissionRequest, _=Depends(require_admin_token)):
    store = get_store()
    task = store.reject_submission(task_id, payload.note)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not awaiting verification.")
    build_candidates_for_task(store, task)
    return {"success": True, "task": task.model_dump(mode="json")}


@router.get("/ledger", response_class=JSONResponse)
def admin_ledger(_=Depends(require_admin_token)):
    store = get_store()
    return {"total": len(store.ledger_entries), "entries": [e.model_dump(mode="json") for e in store.list_ledger_entries()]}
