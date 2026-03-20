"""Task business logic."""
from __future__ import annotations

from ....database import AgentRecord, SQLiteStore, get_store
from ..matching.service import (
    auto_tag_task,
    build_candidates_for_task,
    poll_recommended_tasks,
)
from ..matching.llm import structurize_task
from ..task.schema import (
    CreateTaskRequest,
    DeliverableSpec,
    TaskPayload,
)
from ..user.schema import NaturalLanguageTaskRequest


def create_task(payload: CreateTaskRequest) -> TaskPayload:
    store = get_store()
    task = store.create_task(payload)
    # auto-tag from goal text if LLM not used (manual creation)
    structured = structurize_task(task.goal or task.title, task.reward)
    auto_tag_task(task, structured.get("tags", []), structured.get("skills_required", []), structured.get("region", "global"))
    if task.category == "general" and structured.get("category") != "general":
        task.category = structured["category"]
    store._save_task(task)
    build_candidates_for_task(store, task)
    return task


def create_task_for_user(user, payload: CreateTaskRequest) -> TaskPayload:
    store = get_store()
    task = store.create_task_for_user(user, payload)
    structured = structurize_task(task.goal or task.title, task.reward)
    auto_tag_task(task, structured.get("tags", []), structured.get("skills_required", []), structured.get("region", "global"))
    if task.category == "general" and structured.get("category") != "general":
        task.category = structured["category"]
    store._save_task(task)
    build_candidates_for_task(store, task)
    return task


def create_nl_task_for_user(user, payload: NaturalLanguageTaskRequest) -> tuple[TaskPayload, dict]:
    """Natural-language task: structurize then create."""
    structured = structurize_task(payload.description, payload.max_budget)

    deliverable_dict = structured.get("deliverable", {})
    task_request = CreateTaskRequest(
        category=structured.get("category", "general"),
        title=structured.get("title", payload.description[:60]),
        goal=structured.get("goal", payload.description),
        constraints=structured.get("constraints", []),
        deliverable=DeliverableSpec(**deliverable_dict) if isinstance(deliverable_dict, dict) else DeliverableSpec(),
        acceptance_criteria=structured.get("acceptance_criteria", []),
        reward=structured.get("reward", payload.max_budget),
        sla_seconds=structured.get("sla_seconds", 3600),
    )

    store = get_store()
    task = store.create_task_for_user(user, task_request)
    auto_tag_task(task, structured.get("tags", []), structured.get("skills_required", []), structured.get("region", "global"))
    if task.category == "general" and structured.get("category") != "general":
        task.category = structured["category"]
    store._save_task(task)
    build_candidates_for_task(store, task)
    return task, structured


def poll_tasks(agent: AgentRecord, categories: list[str], max_tasks: int) -> list[dict]:
    store = get_store()
    return poll_recommended_tasks(store, agent, categories, max_tasks)


def accept_task(task_id: str, agent: AgentRecord, execution_plan=None) -> TaskPayload | None:
    store = get_store()
    return store.accept_task(task_id, agent, execution_plan)


def reject_task(task_id: str, agent: AgentRecord) -> TaskPayload | None:
    store = get_store()
    task = store.reject_task(task_id, agent)
    if task:
        build_candidates_for_task(store, task)
    return task


def submit_proposal(task_id: str, agent: AgentRecord, *, plan_steps, estimated_total_minutes, message):
    store = get_store()
    return store.submit_proposal(
        task_id, agent,
        plan_steps=plan_steps,
        estimated_total_minutes=estimated_total_minutes,
        message=message,
    )


def list_assigned_tasks(agent: AgentRecord):
    store = get_store()
    return store.list_assigned_tasks_for_agent(agent.agent_id)


def update_progress(task_id: str, progress: int, message: str):
    return get_store().update_progress(task_id, progress, message)


def update_step_progress(task_id: str, agent: AgentRecord, step_number: int, step_status: str, message: str):
    store = get_store()
    return store.update_step_progress(task_id, agent, step_number, step_status, message)


def submit_task(task_id: str, agent, *, output, proof, stats):
    return get_store().submit_task(task_id, agent, output=output, proof=proof, stats=stats)
