"""Matching domain – shared schemas."""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..task.schema import SettlementState


class CandidateMatch:
    """A scored match between a task and an agent (plain object, not Pydantic)."""
    __slots__ = ("task_id", "agent_id", "score", "matched_tags", "reason")

    def __init__(
        self,
        task_id: str = "",
        agent_id: str = "",
        score: float = 0.0,
        matched_tags: list[str] | None = None,
        reason: str = "",
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        self.score = score
        self.matched_tags = matched_tags or []
        self.reason = reason


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
