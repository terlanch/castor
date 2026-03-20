"""Admin business logic helpers."""
from __future__ import annotations

from ....database import AgentRecord, get_store
from ..task.schema import TaskPayload


def build_agent_admin_payload(agent: AgentRecord) -> dict:
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.registration.agent_name,
        "description": agent.registration.description,
        "status": agent.status.value,
        "healthy": agent.healthy,
        "current_load": agent.current_load,
        "max_load": agent.max_load,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "balance": agent.balance,
        "api_key": agent.api_key[:12] + "…",
        "verification_code": "***",
        "skills": agent.registration.skills,
        "categories": agent.registration.categories,
        "region": agent.registration.region,
        "reputation": agent.reputation,
    }


def build_task_admin_payload(task: TaskPayload) -> dict:
    return task.model_dump(mode="json")
