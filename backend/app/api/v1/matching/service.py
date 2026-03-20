"""Matching / recommendation service.

Handles candidate pool construction, scoring, and smart polling.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .schema import CandidateMatch
from .taxonomy import TAG_DIMENSIONS
from ..task.schema import TaskPayload, TaskStatus

if TYPE_CHECKING:
    from ....database import AgentRecord, SQLiteStore


# ═══════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════

def compute_match_score(
    *,
    task_tags: list[str],
    task_category: str,
    task_region: str,
    task_reward: int,
    agent_skills: list[str],
    agent_categories: list[str],
    agent_region: str,
    agent_pricing: dict[str, int],
    agent_reputation: dict[str, float],
) -> CandidateMatch:
    """Score a single (task, agent) pair.  Returns a ``CandidateMatch``."""
    matched_tags: list[str] = []
    reasons: list[str] = []
    score = 0.0

    # 1. Tag / skill overlap (0-40)
    agent_set = set(agent_skills) | set(agent_categories)
    task_set = set(task_tags)
    overlap = agent_set & task_set
    matched_tags = sorted(overlap)
    tag_ratio = len(overlap) / len(task_set) if task_set else 0.5
    score += min(40.0, tag_ratio * 40.0)
    if overlap:
        reasons.append(f"{len(overlap)} matching tag(s): {','.join(sorted(overlap))}")

    # 2. Category match (0-20)
    if task_category in agent_categories:
        score += 20.0
        reasons.append(f"Category match: {task_category}")
    elif not agent_categories:
        score += 10.0
        reasons.append("Agent has no category restriction")

    # 3. Region match (0-20)
    if task_region == agent_region:
        score += 20.0
        reasons.append(f"Region match: {task_region}")
    elif agent_region == "global" or task_region == "global":
        score += 10.0
        reasons.append("Global region match")

    # 4. Reputation (0-20)
    cr = agent_reputation.get("completion_rate", 0.5)
    vr = agent_reputation.get("verification_pass_rate", 0.5)
    rep = cr * 10.0 + vr * 10.0
    score += rep
    reasons.append(f"Reputation score: {rep:.0f}")

    return CandidateMatch(
        score=round(score, 1),
        matched_tags=matched_tags,
        reason="; ".join(reasons) or "No special match",
    )


# ═══════════════════════════════════════════════════════════════════════
# Candidate pool management
# ═══════════════════════════════════════════════════════════════════════

def _score_pair(task: TaskPayload, agent: "AgentRecord") -> CandidateMatch | None:
    reg = agent.registration
    result = compute_match_score(
        task_tags=task.tags,
        task_category=task.category,
        task_region=task.task_region,
        task_reward=task.reward,
        agent_skills=reg.skills,
        agent_categories=reg.categories,
        agent_region=reg.region,
        agent_pricing=reg.pricing,
        agent_reputation=agent.reputation,
    )
    if result.score < 10:
        return None
    result.task_id = task.task_id
    result.agent_id = agent.agent_id
    return result


def build_candidates_for_task(store: "SQLiteStore", task: TaskPayload) -> list[CandidateMatch]:
    """Compute candidate agents for a newly created/re-queued task."""
    candidates: list[CandidateMatch] = []
    for agent in store.agents.values():
        if agent.agent_id in task.rejected_agent_ids:
            continue
        match = _score_pair(task, agent)
        if match:
            candidates.append(match)
            store.save_candidate(match)
    candidates.sort(key=lambda c: c.score, reverse=True)
    store.candidate_pool[task.task_id] = candidates
    return candidates


def build_candidates_for_agent(store: "SQLiteStore", agent: "AgentRecord") -> list[CandidateMatch]:
    """Compute candidate tasks for a newly registered agent."""
    matches: list[CandidateMatch] = []
    for task in store.tasks.values():
        if task.status != TaskStatus.queued:
            continue
        if agent.agent_id in task.rejected_agent_ids:
            continue
        match = _score_pair(task, agent)
        if match:
            matches.append(match)
            store.save_candidate(match)
            store.candidate_pool.setdefault(task.task_id, []).append(match)
    return matches


def auto_tag_task(task: TaskPayload, tags: list[str], skills: list[str], region: str) -> None:
    """Apply extracted tags onto a task payload."""
    if not task.tags:
        task.tags = tags
    if not task.skills_required:
        task.skills_required = skills
    if task.task_region == "global" and region != "global":
        task.task_region = region


# ═══════════════════════════════════════════════════════════════════════
# Smart polling
# ═══════════════════════════════════════════════════════════════════════

def poll_recommended_tasks(
    store: "SQLiteStore",
    agent: "AgentRecord",
    categories: list[str],
    max_tasks: int,
) -> list[dict]:
    """Return tasks for this agent, scored and sorted.

    Each item is a dict with full task payload + match metadata:
      { ...task_fields, match_score, matched_tags, match_reason }

    1. Pre-computed candidate pool (sorted by score desc).
    2. Fallback full-scan for un-pooled tasks.
    """
    from ....config import HEARTBEAT_TIMEOUT_SECONDS

    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)

    seen: set[str] = set()
    scored: list[tuple[float, dict]] = []

    # Phase 1: candidate pool
    for task_id, candidates in store.candidate_pool.items():
        for cand in candidates:
            if cand.agent_id != agent.agent_id:
                continue
            task = store.tasks.get(task_id)
            if not task or task.status != TaskStatus.queued:
                continue
            if agent.agent_id in task.rejected_agent_ids:
                continue
            if categories and task.category not in categories:
                continue
            item = task.model_dump(mode="json")
            item["match_score"] = cand.score
            item["matched_tags"] = cand.matched_tags
            item["match_reason"] = cand.reason
            scored.append((cand.score, item))
            seen.add(task_id)

    # Phase 2: fallback
    for task in store.tasks.values():
        if task.task_id in seen or task.status != TaskStatus.queued:
            continue
        if agent.agent_id in task.rejected_agent_ids:
            continue
        if categories and task.category not in categories:
            continue
        if agent.registration.categories and task.category not in agent.registration.categories:
            continue
        match = _score_pair(task, agent)
        fb_score = match.score if match else 0.0
        item = task.model_dump(mode="json")
        item["match_score"] = fb_score
        item["matched_tags"] = match.matched_tags if match else []
        item["match_reason"] = match.reason if match else "No special match"
        scored.append((fb_score, item))
        if match:
            store.save_candidate(match)
            store.candidate_pool.setdefault(task.task_id, []).append(match)

    scored.sort(key=lambda p: p[0], reverse=True)
    return [item for _, item in scored[:max_tasks]]
