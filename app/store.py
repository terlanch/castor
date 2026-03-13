from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from secrets import choice, token_urlsafe
from threading import Lock
from uuid import uuid4

from .models import (
    AgentRegisterRequest,
    AgentStatus,
    CreateTaskRequest,
    DeliverableSpec,
    LedgerEntry,
    SettlementState,
    TaskPayload,
    TaskStatus,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_verification_code() -> str:
    prefixes = ["lagoon", "reef", "harbor", "delta", "cosmos", "anchor"]
    suffix = "".join(choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
    return f"{choice(prefixes)}-{suffix}"


@dataclass
class AgentRecord:
    agent_id: str
    api_key: str
    verification_code: str
    registration: AgentRegisterRequest
    status: AgentStatus = AgentStatus.offline
    current_load: int = 0
    max_load: int = 1
    healthy: bool = False
    last_heartbeat_at: str | None = None
    balance: int = 0
    reputation: dict[str, float] = field(
        default_factory=lambda: {
            "acceptance_rate": 1.0,
            "completion_rate": 1.0,
            "timeout_rate": 0.0,
            "verification_pass_rate": 1.0,
        }
    )


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent.parent / "data" / "castor.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.agents: dict[str, AgentRecord] = {}
        self.api_keys: dict[str, str] = {}
        self.tasks: dict[str, TaskPayload] = {}
        self.ledger_entries: list[LedgerEntry] = []
        self.progress_logs: dict[str, list[dict[str, str | int]]] = {}
        self._init_db()
        self._load_state()
        self._seed_demo_tasks()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL UNIQUE,
                    verification_code TEXT NOT NULL,
                    registration_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_load INTEGER NOT NULL,
                    max_load INTEGER NOT NULL,
                    healthy INTEGER NOT NULL,
                    last_heartbeat_at TEXT,
                    balance INTEGER NOT NULL,
                    reputation_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ledger_entries (
                    entry_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS progress_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_json TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def _load_state(self) -> None:
        self._load_agents()
        self._load_tasks()
        self._load_ledger_entries()
        self._load_progress_logs()

    def _load_agents(self) -> None:
        rows = self._conn.execute("SELECT * FROM agents").fetchall()
        for row in rows:
            registration = AgentRegisterRequest.model_validate(json.loads(row["registration_json"]))
            agent = AgentRecord(
                agent_id=row["agent_id"],
                api_key=row["api_key"],
                verification_code=row["verification_code"],
                registration=registration,
                status=AgentStatus(row["status"]),
                current_load=row["current_load"],
                max_load=row["max_load"],
                healthy=bool(row["healthy"]),
                last_heartbeat_at=row["last_heartbeat_at"],
                balance=row["balance"],
                reputation=json.loads(row["reputation_json"]),
            )
            self.agents[agent.agent_id] = agent
            self.api_keys[agent.api_key] = agent.agent_id

    def _load_tasks(self) -> None:
        rows = self._conn.execute("SELECT payload_json FROM tasks").fetchall()
        for row in rows:
            task = TaskPayload.model_validate(json.loads(row["payload_json"]))
            self.tasks[task.task_id] = task

    def _load_ledger_entries(self) -> None:
        rows = self._conn.execute("SELECT payload_json FROM ledger_entries").fetchall()
        self.ledger_entries = [LedgerEntry.model_validate(json.loads(row["payload_json"])) for row in rows]

    def _load_progress_logs(self) -> None:
        rows = self._conn.execute("SELECT task_id, event_json FROM progress_logs ORDER BY id").fetchall()
        for row in rows:
            self.progress_logs.setdefault(row["task_id"], []).append(json.loads(row["event_json"]))

    def _save_agent(self, agent: AgentRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agents (
                    agent_id, api_key, verification_code, registration_json, status, current_load,
                    max_load, healthy, last_heartbeat_at, balance, reputation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    api_key = excluded.api_key,
                    verification_code = excluded.verification_code,
                    registration_json = excluded.registration_json,
                    status = excluded.status,
                    current_load = excluded.current_load,
                    max_load = excluded.max_load,
                    healthy = excluded.healthy,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    balance = excluded.balance,
                    reputation_json = excluded.reputation_json
                """,
                (
                    agent.agent_id,
                    agent.api_key,
                    agent.verification_code,
                    json.dumps(agent.registration.model_dump(mode="json"), ensure_ascii=False),
                    agent.status.value,
                    agent.current_load,
                    agent.max_load,
                    int(agent.healthy),
                    agent.last_heartbeat_at,
                    agent.balance,
                    json.dumps(agent.reputation, ensure_ascii=False),
                ),
            )
            self._conn.commit()

    def _save_task(self, task: TaskPayload) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tasks (task_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (task.task_id, json.dumps(task.model_dump(mode="json"), ensure_ascii=False)),
            )
            self._conn.commit()

    def _save_ledger_entry(self, entry: LedgerEntry) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO ledger_entries (entry_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (entry.entry_id, json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)),
            )
            self._conn.commit()

    def _save_progress_event(self, task_id: str, event: dict[str, str | int]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO progress_logs (task_id, event_json) VALUES (?, ?)",
                (task_id, json.dumps(event, ensure_ascii=False)),
            )
            self._conn.commit()

    def register_agent(self, payload: AgentRegisterRequest) -> AgentRecord:
        agent_id = str(uuid4())
        api_key = f"castor_sk_{token_urlsafe(24)}"
        record = AgentRecord(
            agent_id=agent_id,
            api_key=api_key,
            verification_code=generate_verification_code(),
            registration=payload,
            max_load=payload.concurrency,
        )
        self.agents[agent_id] = record
        self.api_keys[api_key] = agent_id
        self._save_agent(record)
        return record

    def get_agent_by_api_key(self, api_key: str) -> AgentRecord | None:
        agent_id = self.api_keys.get(api_key)
        if not agent_id:
            return None
        return self.agents.get(agent_id)

    def create_task(self, payload: CreateTaskRequest) -> TaskPayload:
        goal = payload.goal or payload.input.get("query") or payload.title
        deliverable = payload.deliverable
        output_schema = payload.output_schema or deliverable.schema
        if not deliverable.schema and output_schema:
            deliverable = DeliverableSpec(
                format=deliverable.format or "json",
                description=deliverable.description,
                schema=output_schema,
                examples=deliverable.examples,
            )
        task = TaskPayload(
            task_id=f"tsk_{uuid4().hex[:12]}",
            category=payload.category,
            title=payload.title,
            goal=goal,
            constraints=payload.constraints,
            deliverable=deliverable,
            acceptance_criteria=payload.acceptance_criteria,
            input=payload.input,
            output_schema=output_schema,
            reward=payload.reward,
            currency=payload.currency,
            priority=payload.priority,
            sla_seconds=payload.sla_seconds,
            verification_rule=payload.verification_rule,
            retry_policy=payload.retry_policy,
            compliance=payload.compliance,
        )
        self.tasks[task.task_id] = task
        self._save_task(task)
        return task

    def poll_tasks(self, agent: AgentRecord, categories: list[str], max_tasks: int) -> list[TaskPayload]:
        available: list[TaskPayload] = []
        for task in self.tasks.values():
            if task.status != TaskStatus.queued:
                continue
            if categories and task.category not in categories:
                continue
            if agent.registration.categories and task.category not in agent.registration.categories:
                continue
            available.append(task)
            if len(available) >= max_tasks:
                break
        return available

    def accept_task(self, task_id: str, agent: AgentRecord) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.queued:
            return None
        if agent.current_load >= agent.max_load:
            return None
        task.status = TaskStatus.assigned
        task.assigned_agent_id = agent.agent_id
        agent.current_load += 1
        self._save_task(task)
        self._save_agent(agent)
        return task

    def reject_task(self, task_id: str, agent: AgentRecord) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        if task.assigned_agent_id == agent.agent_id and agent.current_load > 0:
            agent.current_load -= 1
        task.status = TaskStatus.rejected
        task.assigned_agent_id = None
        self._save_task(task)
        self._save_agent(agent)
        return task

    def update_progress(self, task_id: str, progress: int, message: str) -> dict[str, str | int] | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.progress = progress
        event = {"at": utc_now(), "progress": progress, "message": message}
        self.progress_logs.setdefault(task_id, []).append(event)
        self._save_task(task)
        self._save_progress_event(task_id, event)
        return event

    def submit_task(self, task_id: str, agent: AgentRecord) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.assigned_agent_id != agent.agent_id:
            return None
        task.status = TaskStatus.completed
        task.progress = 100
        if agent.current_load > 0:
            agent.current_load -= 1
        agent.balance += task.reward
        ledger_entry = LedgerEntry(
            entry_id=f"led_{uuid4().hex[:12]}",
            agent_id=agent.agent_id,
            task_id=task.task_id,
            amount=task.reward,
            currency=task.currency,
            settlement_state=SettlementState.credited,
            note="Auto verified by MVP verification flow.",
        )
        self.ledger_entries.append(ledger_entry)
        self._save_task(task)
        self._save_agent(agent)
        self._save_ledger_entry(ledger_entry)
        return task

    def ledger_for_agent(self, agent_id: str) -> list[LedgerEntry]:
        return [entry for entry in self.ledger_entries if entry.agent_id == agent_id]

    def _seed_demo_tasks(self) -> None:
        if self.tasks:
            return
        demo_tasks = [
            CreateTaskRequest(
                category="buyer_discovery",
                title="Find Russian diesel engine buyers",
                goal="寻找俄罗斯柴油发动机采购商，并输出结构化公司线索清单。",
                constraints=[
                    "优先提供真实存在且可验证的公司信息",
                    "至少提供 3 个候选采购商",
                ],
                deliverable=DeliverableSpec(
                    format="json",
                    description="返回包含 companies 数组的结构化线索结果。",
                    schema={
                        "type": "object",
                        "required": ["companies"],
                        "properties": {
                            "companies": {
                                "type": "array",
                                "minItems": 3,
                            }
                        },
                    },
                ),
                acceptance_criteria=[
                    "companies 字段必须存在",
                    "companies 数量不少于 3",
                    "每条结果应可追溯到公开来源",
                ],
                input={"query": "寻找俄罗斯柴油发动机采购商", "market": "Russia"},
                output_schema={
                    "type": "object",
                    "required": ["companies"],
                    "properties": {
                        "companies": {
                            "type": "array",
                            "minItems": 3,
                        }
                    },
                },
                reward=50,
            ),
            CreateTaskRequest(
                category="supplier_research",
                title="Build agrochemical supplier shortlist",
                goal="筛选东南亚农化供应商，并输出结构化候选名单。",
                constraints=[
                    "至少提供 5 家候选供应商",
                    "结果应适合后续人工复核",
                ],
                deliverable=DeliverableSpec(
                    format="json",
                    description="返回包含 suppliers 数组的结构化供应商名单。",
                    schema={
                        "type": "object",
                        "required": ["suppliers"],
                        "properties": {
                            "suppliers": {
                                "type": "array",
                                "minItems": 5,
                            }
                        },
                    },
                ),
                acceptance_criteria=[
                    "suppliers 字段必须存在",
                    "suppliers 数量不少于 5",
                    "每条结果应至少包含基本身份信息",
                ],
                input={"query": "筛选东南亚农化供应商", "market": "Southeast Asia"},
                output_schema={
                    "type": "object",
                    "required": ["suppliers"],
                    "properties": {
                        "suppliers": {
                            "type": "array",
                            "minItems": 5,
                        }
                    },
                },
                reward=35,
            ),
        ]
        for task in demo_tasks:
            self.create_task(task)
