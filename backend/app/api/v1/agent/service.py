"""Agent business logic."""
from __future__ import annotations

from ....database import AgentRecord, SQLiteStore, get_store
from ..matching.service import build_candidates_for_agent
from .schema import AgentRegisterRequest, AgentStatus, HeartbeatRequest


def register(payload: AgentRegisterRequest) -> AgentRecord:
    store = get_store()
    agent = store.register_agent(payload)
    build_candidates_for_agent(store, agent)
    return agent


def heartbeat(agent: AgentRecord, payload: HeartbeatRequest) -> AgentRecord:
    store = get_store()
    return store.update_agent_heartbeat(
        agent,
        status=payload.status,
        current_load=payload.current_load,
        max_load=payload.max_load,
        healthy=payload.healthy,
    )
