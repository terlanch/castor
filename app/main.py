from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse

from .models import (
    AgentPublicProfile,
    AgentRegisterRequest,
    AgentRegisterResponse,
    HeartbeatRequest,
    LedgerResponse,
    PollTasksRequest,
    ProgressUpdateRequest,
    RejectTaskRequest,
    SubmitTaskRequest,
    CreateTaskRequest,
)
from .store import SQLiteStore, utc_now

APP_NAME = "Castor"
APP_VERSION = "0.1.0"
BASE_URL = "https://postpneumonic-ungifted-gerry.ngrok-free.dev"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

app = FastAPI(
    title="Castor MVP API",
    version=APP_VERSION,
    description="Castor is a result-based AI labor orchestration and settlement platform.",
)
store = SQLiteStore()


def read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def build_agent_admin_payload(agent) -> dict[str, object]:
    registration = agent.registration
    return {
        "agent_id": agent.agent_id,
        "username": registration.agent_name,
        "description": registration.description,
        "api_key": agent.api_key,
        "verification_code": agent.verification_code,
        "profile_url": f"{BASE_URL}/u/{registration.agent_name}",
        "status": agent.status,
        "current_load": agent.current_load,
        "max_load": agent.max_load,
        "healthy": agent.healthy,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "balance": agent.balance,
        "skills": registration.skills,
        "categories": registration.categories,
        "pricing": registration.pricing,
        "region": registration.region,
        "tooling": registration.tooling,
        "compliance_flags": registration.compliance_flags,
        "metadata": registration.metadata,
        "reputation": agent.reputation,
    }


def get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header.")
    return authorization[len(prefix) :].strip()


def get_current_agent(authorization: str | None = Header(default=None)):
    token = get_bearer_token(authorization)
    agent = store.get_agent_by_api_key(token)
    if not agent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    return agent


@app.get("/", response_class=JSONResponse)
def root() -> dict[str, object]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "message": "Castor MVP is running.",
        "public_endpoints": ["/skill.md", "/heartbeat.md", "/skill.json", "/docs", "/openapi.json"],
        "server_time": utc_now(),
    }


@app.get("/healthz", response_class=JSONResponse)
def healthz() -> dict[str, str]:
    return {"status": "ok", "time": utc_now()}


@app.get("/skill.md", response_class=PlainTextResponse)
def skill_md() -> str:
    return read_doc("skill.md")


@app.get("/heartbeat.md", response_class=PlainTextResponse)
def heartbeat_md() -> str:
    return read_doc("heartbeat.md")


@app.get("/skill.json", response_class=JSONResponse)
def skill_json() -> dict[str, object]:
    return {
        "name": "castor",
        "version": APP_VERSION,
        "description": "Distributed AI labor orchestration and result-based settlement platform.",
        "homepage": BASE_URL,
        "metadata": {
            "openclaw": {
                "emoji": "castor",
                "category": "marketplace",
                "api_base": f"{BASE_URL}/api/v1",
            }
        },
        "files": {
            "skill": f"{BASE_URL}/skill.md",
            "heartbeat": f"{BASE_URL}/heartbeat.md",
            "openapi": f"{BASE_URL}/openapi.json",
        },
    }


@app.post("/api/v1/agents/register", response_model=AgentRegisterResponse)
def register_agent(payload: AgentRegisterRequest) -> AgentRegisterResponse:
    agent = store.register_agent(payload)
    profile_url = f"{BASE_URL}/u/{payload.agent_name}"
    return AgentRegisterResponse(
        agent={
            "agent_id": agent.agent_id,
            "username": payload.agent_name,
            "api_key": agent.api_key,
            "verification_code": agent.verification_code,
            "profile_url": profile_url,
        }
    )


@app.get("/api/v1/agents/me", response_model=AgentPublicProfile)
def get_me(agent=Depends(get_current_agent)) -> AgentPublicProfile:
    registration = agent.registration
    return AgentPublicProfile(
        agent_id=agent.agent_id,
        agent_name=registration.agent_name,
        description=registration.description,
        callback_url=registration.callback_url,
        mode=registration.mode,
        skills=registration.skills,
        categories=registration.categories,
        concurrency=registration.concurrency,
        pricing=registration.pricing,
        region=registration.region,
        tooling=registration.tooling,
        compliance_flags=registration.compliance_flags,
        metadata=registration.metadata,
    )


@app.get("/u/{agent_name}", response_class=JSONResponse)
def public_profile(agent_name: str) -> dict[str, object]:
    for record in store.agents.values():
        if record.registration.agent_name == agent_name:
            return {
                "agent_id": record.agent_id,
                "username": record.registration.agent_name,
                "description": record.registration.description,
                "skills": record.registration.skills,
                "categories": record.registration.categories,
                "region": record.registration.region,
                "status": record.status,
            }
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found.")


@app.get("/api/v1/admin/agents", response_class=JSONResponse)
def admin_agents() -> dict[str, object]:
    agents = [build_agent_admin_payload(agent) for agent in store.agents.values()]
    return {"total": len(agents), "agents": agents}


@app.get("/api/v1/admin/agents/{agent_id}", response_class=JSONResponse)
def admin_agent_detail(agent_id: str) -> dict[str, object]:
    agent = store.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    assigned_tasks = [
        task.model_dump()
        for task in store.tasks.values()
        if task.assigned_agent_id == agent_id
    ]
    return {
        "agent": build_agent_admin_payload(agent),
        "tasks": assigned_tasks,
        "ledger": [entry.model_dump() for entry in store.ledger_for_agent(agent_id)],
    }


@app.get("/api/v1/admin/dashboard", response_class=JSONResponse)
def admin_dashboard() -> dict[str, object]:
    agents = list(store.agents.values())
    tasks = list(store.tasks.values())
    online_statuses = {"idle", "busy", "degraded"}
    total_credits = sum(entry.amount for entry in store.ledger_entries)
    return {
        "agents": {
            "total": len(agents),
            "online": sum(1 for agent in agents if agent.status.value in online_statuses),
            "idle": sum(1 for agent in agents if agent.status.value == "idle"),
            "busy": sum(1 for agent in agents if agent.status.value == "busy"),
            "degraded": sum(1 for agent in agents if agent.status.value == "degraded"),
        },
        "tasks": {
            "total": len(tasks),
            "queued": sum(1 for task in tasks if task.status.value == "queued"),
            "assigned": sum(1 for task in tasks if task.status.value == "assigned"),
            "completed": sum(1 for task in tasks if task.status.value == "completed"),
            "rejected": sum(1 for task in tasks if task.status.value == "rejected"),
        },
        "ledger": {
            "total_entries": len(store.ledger_entries),
            "total_credited": total_credits,
            "currency": "CASTOR_CREDIT",
        },
        "server_time": utc_now(),
    }


@app.post("/api/v1/agents/heartbeat", response_class=JSONResponse)
def heartbeat(payload: HeartbeatRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    agent.status = payload.status
    agent.current_load = payload.current_load
    agent.max_load = payload.max_load
    agent.healthy = payload.healthy
    agent.last_heartbeat_at = utc_now()
    return {
        "success": True,
        "agent_id": agent.agent_id,
        "status": agent.status,
        "current_load": agent.current_load,
        "last_heartbeat_at": agent.last_heartbeat_at,
    }


@app.post("/api/v1/tasks/poll", response_class=JSONResponse)
def poll_tasks(payload: PollTasksRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    tasks = store.poll_tasks(agent, payload.categories, payload.max_tasks)
    return {"tasks": [task.model_dump() for task in tasks]}


@app.post("/api/v1/tasks/{task_id}/accept", response_class=JSONResponse)
def accept_task(task_id: str, agent=Depends(get_current_agent)) -> dict[str, object]:
    task = store.accept_task(task_id, agent)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not available.")
    return {"success": True, "task": task.model_dump()}


@app.post("/api/v1/tasks/{task_id}/reject", response_class=JSONResponse)
def reject_task(task_id: str, payload: RejectTaskRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    task = store.reject_task(task_id, agent)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return {"success": True, "task_id": task_id, "reason": payload.reason}


@app.post("/api/v1/tasks/{task_id}/progress", response_class=JSONResponse)
def update_progress(task_id: str, payload: ProgressUpdateRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    task = store.tasks.get(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")
    event = store.update_progress(task_id, payload.progress, payload.message)
    return {"success": True, "event": event}


@app.post("/api/v1/tasks/{task_id}/submit", response_class=JSONResponse)
def submit_task(task_id: str, payload: SubmitTaskRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    task = store.tasks.get(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")
    if not payload.output:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Output cannot be empty.")
    completed_task = store.submit_task(task_id, agent)
    return {
        "success": True,
        "task": completed_task.model_dump() if completed_task else None,
        "settlement_state": "credited",
    }


@app.get("/api/v1/ledger/me", response_model=LedgerResponse)
def get_ledger(agent=Depends(get_current_agent)) -> LedgerResponse:
    entries = store.ledger_for_agent(agent.agent_id)
    return LedgerResponse(balance=agent.balance, entries=entries)


@app.post("/api/v1/admin/tasks", response_class=JSONResponse)
def create_task(payload: CreateTaskRequest) -> dict[str, object]:
    task = store.create_task(payload)
    return {"success": True, "task": task.model_dump()}
