from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    PaymentState,
    SettlementState,
    UserLoginRequest,
    UserRegisterRequest,
    TaskSubmission,
    TaskPayload,
    TaskStatus,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def generate_verification_code() -> str:
    prefixes = ["lagoon", "reef", "harbor", "delta", "cosmos", "anchor"]
    suffix = "".join(choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
    return f"{choice(prefixes)}-{suffix}"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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


@dataclass
class UserRecord:
    user_id: str
    username: str
    password_hash: str
    display_name: str
    access_token: str
    balance: int = 0
    frozen_balance: int = 0


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent.parent / "data" / "castor.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.users: dict[str, UserRecord] = {}
        self.user_tokens: dict[str, str] = {}
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

                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    access_token TEXT NOT NULL UNIQUE,
                    balance INTEGER NOT NULL,
                    frozen_balance INTEGER NOT NULL
                );
                """
            )
            self._conn.commit()

    def _load_state(self) -> None:
        self._load_users()
        self._load_agents()
        self._load_tasks()
        self._load_ledger_entries()
        self._load_progress_logs()

    def _load_users(self) -> None:
        rows = self._conn.execute("SELECT * FROM users").fetchall()
        for row in rows:
            user = UserRecord(
                user_id=row["user_id"],
                username=row["username"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                access_token=row["access_token"],
                balance=row["balance"],
                frozen_balance=row["frozen_balance"],
            )
            self.users[user.user_id] = user
            self.user_tokens[user.access_token] = user.user_id

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

    def _save_user(self, user: UserRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (
                    user_id, username, password_hash, display_name, access_token, balance, frozen_balance
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    display_name = excluded.display_name,
                    access_token = excluded.access_token,
                    balance = excluded.balance,
                    frozen_balance = excluded.frozen_balance
                """,
                (
                    user.user_id,
                    user.username,
                    user.password_hash,
                    user.display_name,
                    user.access_token,
                    user.balance,
                    user.frozen_balance,
                ),
            )
            self._conn.commit()

    def find_agent_by_name(self, agent_name: str) -> AgentRecord | None:
        for agent in self.agents.values():
            if agent.registration.agent_name == agent_name:
                return agent
        return None

    def find_user_by_username(self, username: str) -> UserRecord | None:
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def get_user_by_token(self, access_token: str) -> UserRecord | None:
        user_id = self.user_tokens.get(access_token)
        if not user_id:
            return None
        return self.users.get(user_id)

    def register_user(self, payload: UserRegisterRequest) -> UserRecord:
        existing_user = self.find_user_by_username(payload.username)
        if existing_user:
            return existing_user
        user = UserRecord(
            user_id=str(uuid4()),
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name or payload.username,
            access_token=f"castor_usr_{token_urlsafe(24)}",
            balance=0,
            frozen_balance=0,
        )
        self.users[user.user_id] = user
        self.user_tokens[user.access_token] = user.user_id
        self._save_user(user)
        return user

    def login_user(self, payload: UserLoginRequest) -> UserRecord | None:
        user = self.find_user_by_username(payload.username)
        if not user:
            return None
        if user.password_hash != hash_password(payload.password):
            return None
        return user

    def topup_user(self, user: UserRecord, amount: int) -> UserRecord:
        user.balance += amount
        self._save_user(user)
        return user

    def list_user_tasks(self, user_id: str) -> list[TaskPayload]:
        return [task for task in self.tasks.values() if task.owner_user_id == user_id]

    def update_agent_heartbeat(
        self,
        agent: AgentRecord,
        *,
        status: AgentStatus,
        current_load: int,
        max_load: int,
        healthy: bool,
    ) -> AgentRecord:
        agent.status = status
        agent.current_load = current_load
        agent.max_load = max_load
        agent.healthy = healthy
        agent.last_heartbeat_at = utc_now()
        self._save_agent(agent)
        return agent

    def refresh_agent_statuses(self, timeout_seconds: int = 120) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        for agent in self.agents.values():
            last_seen = parse_utc_timestamp(agent.last_heartbeat_at)
            if last_seen and last_seen < threshold and agent.status != AgentStatus.offline:
                agent.status = AgentStatus.offline
                agent.healthy = False
                agent.current_load = 0
                self._save_agent(agent)

    def list_tasks(self) -> list[TaskPayload]:
        return list(self.tasks.values())

    def list_ledger_entries(self) -> list[LedgerEntry]:
        return list(self.ledger_entries)

    def get_task(self, task_id: str) -> TaskPayload | None:
        return self.tasks.get(task_id)

    def list_tasks_for_agent(self, agent_id: str) -> list[TaskPayload]:
        return [task for task in self.tasks.values() if task.assigned_agent_id == agent_id]

    def total_earned_for_agent(self, agent_id: str) -> int:
        return sum(entry.amount for entry in self.ledger_entries if entry.agent_id == agent_id)

    def register_agent(self, payload: AgentRegisterRequest) -> AgentRecord:
        existing_agent = self.find_agent_by_name(payload.agent_name)
        if existing_agent:
            return existing_agent
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

    def create_task_for_user(self, user: UserRecord, payload: CreateTaskRequest) -> TaskPayload:
        if user.balance < payload.reward:
            raise ValueError("Insufficient balance to reserve reward.")
        task = self.create_task(payload)
        task.owner_user_id = user.user_id
        task.owner_username = user.username
        task.payment_state = PaymentState.reserved
        user.balance -= task.reward
        user.frozen_balance += task.reward
        self._save_task(task)
        self._save_user(user)
        return task

    def poll_tasks(self, agent: AgentRecord, categories: list[str], max_tasks: int) -> list[TaskPayload]:
        self.refresh_agent_statuses()
        available: list[TaskPayload] = []
        for task in self.tasks.values():
            if task.status != TaskStatus.queued:
                continue
            if agent.agent_id in task.rejected_agent_ids:
                continue
            if categories and task.category not in categories:
                continue
            if agent.registration.categories and task.category not in agent.registration.categories:
                continue
            available.append(task)
            if len(available) >= max_tasks:
                break
        return available

    def accept_task(self, task_id: str, agent: AgentRecord, execution_plan=None) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.queued:
            return None
        if agent.current_load >= agent.max_load:
            return None
        if agent.agent_id in task.rejected_agent_ids:
            return None
        task.status = TaskStatus.assigned
        task.assigned_agent_id = agent.agent_id
        task.progress = 0
        task.settlement_state = None
        task.verification_note = None
        task.submission = None
        task.execution_plan = execution_plan
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
        if agent.agent_id not in task.rejected_agent_ids:
            task.rejected_agent_ids.append(agent.agent_id)
        task.status = TaskStatus.queued
        task.assigned_agent_id = None
        task.progress = 0
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

    def submit_task(
        self,
        task_id: str,
        agent: AgentRecord,
        *,
        output: dict[str, object],
        proof,
        stats,
    ) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.assigned_agent_id != agent.agent_id:
            return None
        task.status = TaskStatus.submitted
        task.progress = 100
        task.settlement_state = SettlementState.pending_verification
        task.submission = TaskSubmission(
            output=output,
            proof=proof,
            stats=stats,
            submitted_at=utc_now(),
            submitted_by_agent_id=agent.agent_id,
        )
        if agent.current_load > 0:
            agent.current_load -= 1
        self._save_task(task)
        self._save_agent(agent)
        return task

    def verify_task(self, task_id: str, note: str) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.submitted or not task.assigned_agent_id:
            return None
        task.status = TaskStatus.verified
        task.settlement_state = SettlementState.verified
        task.payment_state = PaymentState.awaiting_user_acceptance
        task.verification_note = note
        self._save_task(task)
        return task

    def reject_submission(self, task_id: str, note: str) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.status not in {TaskStatus.submitted, TaskStatus.verified}:
            return None
        agent_id = task.assigned_agent_id
        task.status = TaskStatus.queued
        task.settlement_state = SettlementState.rejected
        task.payment_state = PaymentState.reserved
        task.verification_note = note
        task.assigned_agent_id = None
        task.progress = 0
        task.submission = None
        if agent_id and agent_id not in task.rejected_agent_ids:
            task.rejected_agent_ids.append(agent_id)
        self._save_task(task)
        return task

    def accept_task_result(self, user: UserRecord, task_id: str, note: str) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.owner_user_id != user.user_id or task.status != TaskStatus.verified or not task.assigned_agent_id:
            return None
        agent = self.agents.get(task.assigned_agent_id)
        if not agent:
            return None
        task.status = TaskStatus.completed
        task.settlement_state = SettlementState.credited
        task.payment_state = PaymentState.paid
        task.verification_note = note
        agent.balance += task.reward
        if user.frozen_balance >= task.reward:
            user.frozen_balance -= task.reward
        ledger_entry = LedgerEntry(
            entry_id=f"led_{uuid4().hex[:12]}",
            agent_id=agent.agent_id,
            task_id=task.task_id,
            amount=task.reward,
            currency=task.currency,
            settlement_state=SettlementState.credited,
            note=note,
        )
        self.ledger_entries.append(ledger_entry)
        self._save_task(task)
        self._save_agent(agent)
        self._save_user(user)
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
