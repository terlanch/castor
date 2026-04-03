"""Castor SQLite persistence layer.

Pure data-access; no matching / scoring logic.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import choice, token_urlsafe
from threading import Lock
from typing import Any
from uuid import uuid4

from .api.v1.agent.schema import AgentRegisterRequest, AgentStatus
from .api.v1.task.schema import (
    CreateTaskRequest,
    DeliverableSpec,
    ExecutionPlan,
    PaymentState,
    ProposalStatus,
    SettlementState,
    TaskPayload,
    TaskProposal,
    TaskStatus,
    TaskSubmission,
    UploadedFile,
)
from .api.v1.user.schema import UserLoginRequest, UserRegisterRequest
from .api.v1.matching.schema import CandidateMatch, LedgerEntry


# ── Helpers ────────────────────────────────────────────────────────────

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


# ── Data records ───────────────────────────────────────────────────────

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
    claim_token: str = ""
    owner_user_id: str | None = None
    claimed_at: str | None = None


@dataclass
class AgentClaimSession:
    session_id: str
    agent_id: str
    claim_token: str
    email: str
    username: str
    password_hash: str
    email_verify_token: str
    email_verify_expires_at: str
    status: str = "pending_email"
    email_verified_at: str | None = None
    tweet_url: str | None = None
    tweet_verified_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


# Users created via Google OAuth use this placeholder; local password login is rejected.
PASSWORD_OAUTH_PLACEHOLDER = "__castor_oauth_no_password__"


@dataclass
class UserRecord:
    user_id: str
    username: str
    password_hash: str
    display_name: str
    access_token: str
    balance: int = 0
    frozen_balance: int = 0
    google_sub: str | None = None


# ── Store ──────────────────────────────────────────────────────────────

class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        from .config import DB_PATH as default_path

        self.db_path = Path(db_path) if db_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        self.users: dict[str, UserRecord] = {}
        self.user_tokens: dict[str, str] = {}
        self.agents: dict[str, AgentRecord] = {}
        self.api_keys: dict[str, str] = {}
        self.tasks: dict[str, TaskPayload] = {}
        self.proposals: dict[str, TaskProposal] = {}  # proposal_id → TaskProposal
        self.ledger_entries: list[LedgerEntry] = []
        self.progress_logs: dict[str, list[dict[str, Any]]] = {}
        self.candidate_pool: dict[str, list[CandidateMatch]] = {}
        self.uploaded_files: dict[str, UploadedFile] = {}  # file_id → UploadedFile
        self.claim_sessions: dict[str, AgentClaimSession] = {}  # session_id → session
        self.claim_verify_tokens: dict[str, str] = {}  # email_verify_token → session_id
        self.claim_tokens: dict[str, str] = {}  # claim_token → agent_id

        self._init_db()
        self._load_state()

    # ── DDL ────────────────────────────────────────────────────────────

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
                CREATE TABLE IF NOT EXISTS candidate_pool (
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    matched_tags TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(task_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    file_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    download_url TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL
                );
                """
            )
            self._migrate_schema()
            self._conn.commit()
            self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Lightweight SQLite migrations for existing DB files."""
        with self._lock:
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(users)")}
            if "google_sub" not in cols:
                self._conn.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
                self._conn.commit()
            self._conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
                ON users(google_sub) WHERE google_sub IS NOT NULL AND google_sub != ''
                """
            )
            self._conn.commit()

    def _migrate_schema(self) -> None:
        """Add columns / tables for existing databases."""
        def _cols(table: str) -> set[str]:
            cur = self._conn.execute(f"PRAGMA table_info({table})")
            # Use column name from pragma (row[1] can mis-read with some Row layouts).
            return {str(row["name"]) for row in cur.fetchall()}

        def _add_column_if_absent(table: str, col: str, ddl: str) -> None:
            if col in _cols(table):
                return
            try:
                self._conn.execute(ddl)
            except sqlite3.OperationalError as e:
                err = str(e).lower()
                if "duplicate column name" in err:
                    return
                raise

        # SQLite rejects ADD COLUMN ... UNIQUE; enforce uniqueness via index below.
        _add_column_if_absent("agents", "claim_token", "ALTER TABLE agents ADD COLUMN claim_token TEXT")
        _add_column_if_absent("agents", "owner_user_id", "ALTER TABLE agents ADD COLUMN owner_user_id TEXT")
        _add_column_if_absent("agents", "claimed_at", "ALTER TABLE agents ADD COLUMN claimed_at TEXT")

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_claim_sessions (
                session_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                claim_token TEXT NOT NULL,
                email TEXT NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                email_verify_token TEXT NOT NULL UNIQUE,
                email_verify_expires_at TEXT NOT NULL,
                email_verified_at TEXT,
                tweet_url TEXT,
                tweet_verified_at TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Backfill claim_token for legacy agents
        for row in self._conn.execute(
            "SELECT agent_id FROM agents WHERE claim_token IS NULL OR claim_token = ''"
        ).fetchall():
            tok = token_urlsafe(32)
            self._conn.execute(
                "UPDATE agents SET claim_token = ? WHERE agent_id = ?",
                (tok, row["agent_id"]),
            )

        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_agents_claim_token "
            "ON agents(claim_token)"
        )

    # ── Load ───────────────────────────────────────────────────────────

    def _load_state(self) -> None:
        self._load_users()
        self._load_agents()
        self._load_tasks()
        self._load_proposals()
        self._load_ledger_entries()
        self._load_progress_logs()
        self._load_candidate_pool()
        self._load_uploaded_files()
        self._load_claim_sessions()

    def _load_users(self) -> None:
        for row in self._conn.execute("SELECT * FROM users").fetchall():
            gsub = row["google_sub"] if "google_sub" in row.keys() else None
            user = UserRecord(
                user_id=row["user_id"],
                username=row["username"],
                password_hash=row["password_hash"],
                display_name=row["display_name"],
                access_token=row["access_token"],
                balance=row["balance"],
                frozen_balance=row["frozen_balance"],
                google_sub=gsub,
            )
            self.users[user.user_id] = user
            self.user_tokens[user.access_token] = user.user_id

    def _load_agents(self) -> None:
        self.claim_tokens.clear()
        for row in self._conn.execute("SELECT * FROM agents").fetchall():
            registration = AgentRegisterRequest.model_validate(
                json.loads(row["registration_json"])
            )
            raw_ct = row["claim_token"] if row["claim_token"] else ""
            ct = raw_ct or token_urlsafe(32)
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
                claim_token=ct,
                owner_user_id=row["owner_user_id"],
                claimed_at=row["claimed_at"],
            )
            self.agents[agent.agent_id] = agent
            self.api_keys[agent.api_key] = agent.agent_id
            if agent.claim_token:
                self.claim_tokens[agent.claim_token] = agent.agent_id
            if not raw_ct:
                self._save_agent(agent)

    def _load_claim_sessions(self) -> None:
        self.claim_sessions.clear()
        self.claim_verify_tokens.clear()
        try:
            rows = self._conn.execute("SELECT * FROM agent_claim_sessions").fetchall()
        except sqlite3.OperationalError:
            return
        for row in rows:
            s = AgentClaimSession(
                session_id=row["session_id"],
                agent_id=row["agent_id"],
                claim_token=row["claim_token"],
                email=row["email"],
                username=row["username"],
                password_hash=row["password_hash"],
                email_verify_token=row["email_verify_token"],
                email_verify_expires_at=row["email_verify_expires_at"],
                status=row["status"],
                email_verified_at=row["email_verified_at"],
                tweet_url=row["tweet_url"],
                tweet_verified_at=row["tweet_verified_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            self.claim_sessions[s.session_id] = s
            self.claim_verify_tokens[s.email_verify_token] = s.session_id

    def _load_tasks(self) -> None:
        for row in self._conn.execute("SELECT payload_json FROM tasks").fetchall():
            task = TaskPayload.model_validate(json.loads(row["payload_json"]))
            self.tasks[task.task_id] = task

    def _load_ledger_entries(self) -> None:
        rows = self._conn.execute("SELECT payload_json FROM ledger_entries").fetchall()
        self.ledger_entries = [
            LedgerEntry.model_validate(json.loads(r["payload_json"])) for r in rows
        ]

    def _load_progress_logs(self) -> None:
        rows = self._conn.execute(
            "SELECT task_id, event_json FROM progress_logs ORDER BY id"
        ).fetchall()
        for row in rows:
            self.progress_logs.setdefault(row["task_id"], []).append(
                json.loads(row["event_json"])
            )

    def _load_proposals(self) -> None:
        for row in self._conn.execute("SELECT payload_json FROM proposals").fetchall():
            proposal = TaskProposal.model_validate(json.loads(row["payload_json"]))
            self.proposals[proposal.proposal_id] = proposal

    def _load_candidate_pool(self) -> None:
        rows = self._conn.execute(
            "SELECT task_id, agent_id, score, matched_tags, reason "
            "FROM candidate_pool WHERE status = 'active'"
        ).fetchall()
        for row in rows:
            match = CandidateMatch(
                task_id=row["task_id"],
                agent_id=row["agent_id"],
                score=row["score"],
                matched_tags=json.loads(row["matched_tags"]),
                reason=row["reason"],
            )
            self.candidate_pool.setdefault(row["task_id"], []).append(match)

    # ── Save helpers ───────────────────────────────────────────────────

    def _save_agent(self, agent: AgentRecord) -> None:
        with self._lock:
            old = self.agents.get(agent.agent_id)
            if old and old.claim_token and old.claim_token != agent.claim_token:
                self.claim_tokens.pop(old.claim_token, None)
            self._conn.execute(
                """
                INSERT INTO agents (
                    agent_id, api_key, verification_code, registration_json,
                    status, current_load, max_load, healthy,
                    last_heartbeat_at, balance, reputation_json,
                    claim_token, owner_user_id, claimed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    api_key=excluded.api_key, verification_code=excluded.verification_code,
                    registration_json=excluded.registration_json, status=excluded.status,
                    current_load=excluded.current_load, max_load=excluded.max_load,
                    healthy=excluded.healthy, last_heartbeat_at=excluded.last_heartbeat_at,
                    balance=excluded.balance, reputation_json=excluded.reputation_json,
                    claim_token=excluded.claim_token, owner_user_id=excluded.owner_user_id,
                    claimed_at=excluded.claimed_at
                """,
                (
                    agent.agent_id, agent.api_key, agent.verification_code,
                    json.dumps(agent.registration.model_dump(mode="json"), ensure_ascii=False),
                    agent.status.value, agent.current_load, agent.max_load,
                    int(agent.healthy), agent.last_heartbeat_at, agent.balance,
                    json.dumps(agent.reputation, ensure_ascii=False),
                    agent.claim_token or None,
                    agent.owner_user_id,
                    agent.claimed_at,
                ),
            )
            self._conn.commit()
        if agent.claim_token:
            self.claim_tokens[agent.claim_token] = agent.agent_id

    def _save_claim_session(self, session: AgentClaimSession) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agent_claim_sessions (
                    session_id, agent_id, claim_token, email, username, password_hash,
                    email_verify_token, email_verify_expires_at, email_verified_at,
                    tweet_url, tweet_verified_at, status, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                    agent_id=excluded.agent_id, claim_token=excluded.claim_token,
                    email=excluded.email, username=excluded.username,
                    password_hash=excluded.password_hash,
                    email_verify_token=excluded.email_verify_token,
                    email_verify_expires_at=excluded.email_verify_expires_at,
                    email_verified_at=excluded.email_verified_at,
                    tweet_url=excluded.tweet_url, tweet_verified_at=excluded.tweet_verified_at,
                    status=excluded.status, updated_at=excluded.updated_at
                """,
                (
                    session.session_id, session.agent_id, session.claim_token,
                    session.email, session.username, session.password_hash,
                    session.email_verify_token, session.email_verify_expires_at,
                    session.email_verified_at, session.tweet_url, session.tweet_verified_at,
                    session.status, session.created_at, session.updated_at,
                ),
            )
            self._conn.commit()
        self.claim_sessions[session.session_id] = session
        self.claim_verify_tokens[session.email_verify_token] = session.session_id

    def _save_task(self, task: TaskPayload) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO tasks (task_id, payload_json) VALUES (?,?) "
                "ON CONFLICT(task_id) DO UPDATE SET payload_json=excluded.payload_json",
                (task.task_id, json.dumps(task.model_dump(mode="json"), ensure_ascii=False)),
            )
            self._conn.commit()

    def _save_ledger_entry(self, entry: LedgerEntry) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO ledger_entries (entry_id, payload_json) VALUES (?,?) "
                "ON CONFLICT(entry_id) DO UPDATE SET payload_json=excluded.payload_json",
                (entry.entry_id, json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)),
            )
            self._conn.commit()

    def _save_progress_event(self, task_id: str, event: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO progress_logs (task_id, event_json) VALUES (?,?)",
                (task_id, json.dumps(event, ensure_ascii=False)),
            )
            self._conn.commit()

    def _save_user(self, user: UserRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (
                    user_id, username, password_hash, display_name,
                    access_token, balance, frozen_balance, google_sub
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username, password_hash=excluded.password_hash,
                    display_name=excluded.display_name, access_token=excluded.access_token,
                    balance=excluded.balance, frozen_balance=excluded.frozen_balance,
                    google_sub=excluded.google_sub
                """,
                (
                    user.user_id, user.username, user.password_hash,
                    user.display_name, user.access_token,
                    user.balance, user.frozen_balance, user.google_sub,
                ),
            )
            self._conn.commit()

    def _save_proposal(self, proposal: TaskProposal) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO proposals (proposal_id, task_id, agent_id, payload_json)
                VALUES (?,?,?,?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    payload_json=excluded.payload_json
                """,
                (
                    proposal.proposal_id, proposal.task_id, proposal.agent_id,
                    json.dumps(proposal.model_dump(mode="json"), ensure_ascii=False),
                ),
            )
            self._conn.commit()

    # ── Candidate pool CRUD ────────────────────────────────────────────

    def save_candidate(self, match: CandidateMatch) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO candidate_pool
                    (task_id, agent_id, score, matched_tags, reason, status, created_at)
                VALUES (?,?,?,?,?,'active',?)
                ON CONFLICT(task_id, agent_id) DO UPDATE SET
                    score=excluded.score, matched_tags=excluded.matched_tags,
                    reason=excluded.reason, status='active'
                """,
                (
                    match.task_id, match.agent_id, match.score,
                    json.dumps(match.matched_tags, ensure_ascii=False),
                    match.reason, utc_now(),
                ),
            )
            self._conn.commit()
        self.candidate_pool.setdefault(match.task_id, [])
        pool = self.candidate_pool[match.task_id]
        pool[:] = [c for c in pool if c.agent_id != match.agent_id]
        pool.append(match)

    def clear_candidates_for_task(self, task_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM candidate_pool WHERE task_id=?", (task_id,)
            )
            self._conn.commit()
        self.candidate_pool.pop(task_id, None)

    # ── Agent operations ───────────────────────────────────────────────

    def find_agent_by_name(self, agent_name: str) -> AgentRecord | None:
        for agent in self.agents.values():
            if agent.registration.agent_name == agent_name:
                return agent
        return None

    def get_agent_by_api_key(self, api_key: str) -> AgentRecord | None:
        agent_id = self.api_keys.get(api_key)
        return self.agents.get(agent_id) if agent_id else None

    def register_agent(self, payload: AgentRegisterRequest) -> AgentRecord:
        existing = self.find_agent_by_name(payload.agent_name)
        if existing:
            return existing
        agent_id = str(uuid4())
        api_key = f"castor_sk_{token_urlsafe(24)}"
        record = AgentRecord(
            agent_id=agent_id,
            api_key=api_key,
            verification_code=generate_verification_code(),
            registration=payload,
            max_load=payload.concurrency,
            claim_token=token_urlsafe(32),
        )
        self.agents[agent_id] = record
        self.api_keys[api_key] = agent_id
        self._save_agent(record)
        return record

    def get_agent_by_claim_token(self, claim_token: str) -> AgentRecord | None:
        agent_id = self.claim_tokens.get(claim_token)
        return self.agents.get(agent_id) if agent_id else None

    def get_claim_session_by_verify_token(self, verify_token: str) -> AgentClaimSession | None:
        sid = self.claim_verify_tokens.get(verify_token)
        return self.claim_sessions.get(sid) if sid else None

    def expire_open_claim_sessions_for_agent(self, agent_id: str) -> None:
        for s in list(self.claim_sessions.values()):
            if s.agent_id != agent_id:
                continue
            if s.status in ("completed", "expired"):
                continue
            s.status = "expired"
            s.updated_at = utc_now()
            self._save_claim_session(s)

    def save_claim_session(self, session: AgentClaimSession) -> None:
        self._save_claim_session(session)

    def create_user_from_claim(
        self, *, username: str, password_hash: str, display_name: str
    ) -> UserRecord:
        if self.find_user_by_username(username):
            raise ValueError("username_taken")
        user = UserRecord(
            user_id=str(uuid4()),
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            access_token=f"castor_usr_{token_urlsafe(24)}",
        )
        self.users[user.user_id] = user
        self.user_tokens[user.access_token] = user.user_id
        self._save_user(user)
        return user

    def set_agent_owner(self, agent: AgentRecord, user_id: str) -> None:
        agent.owner_user_id = user_id
        agent.claimed_at = utc_now()
        self._save_agent(agent)

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

    # ── User operations ────────────────────────────────────────────────

    def find_user_by_username(self, username: str) -> UserRecord | None:
        for u in self.users.values():
            if u.username == username:
                return u
        return None

    def find_user_by_google_sub(self, google_sub: str) -> UserRecord | None:
        for u in self.users.values():
            if u.google_sub == google_sub:
                return u
        return None

    def get_user_by_token(self, access_token: str) -> UserRecord | None:
        uid = self.user_tokens.get(access_token)
        return self.users.get(uid) if uid else None

    def register_user(self, payload: UserRegisterRequest) -> UserRecord:
        existing = self.find_user_by_username(payload.username)
        if existing:
            return existing
        user = UserRecord(
            user_id=str(uuid4()),
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name or payload.username,
            access_token=f"castor_usr_{token_urlsafe(24)}",
        )
        self.users[user.user_id] = user
        self.user_tokens[user.access_token] = user.user_id
        self._save_user(user)
        return user

    def login_user(self, payload: UserLoginRequest) -> UserRecord | None:
        user = self.find_user_by_username(payload.username)
        if not user:
            return None
        if user.password_hash == PASSWORD_OAUTH_PLACEHOLDER:
            return None
        if user.password_hash != hash_password(payload.password):
            return None
        return user

    def upsert_google_user(
        self,
        *,
        google_sub: str,
        email: str | None,
        display_name: str | None,
    ) -> UserRecord:
        existing = self.find_user_by_google_sub(google_sub)
        if existing:
            if display_name and display_name != existing.display_name:
                existing.display_name = display_name
                self._save_user(existing)
            return existing

        # Prefer email as username if unused; if taken by another account, fall back to sub-based id.
        base_username: str
        if email and (e := email.strip().lower()[:100]):
            other = self.find_user_by_username(e)
            if not other:
                base_username = e
            else:
                base_username = f"g_{google_sub}"
        else:
            base_username = f"g_{google_sub}"
        if self.find_user_by_username(base_username):
            base_username = f"g_{google_sub}_{uuid4().hex[:8]}"

        user = UserRecord(
            user_id=str(uuid4()),
            username=base_username,
            password_hash=PASSWORD_OAUTH_PLACEHOLDER,
            display_name=(display_name or email or base_username)[:100],
            access_token=f"castor_usr_{token_urlsafe(24)}",
            google_sub=google_sub,
        )
        self.users[user.user_id] = user
        self.user_tokens[user.access_token] = user.user_id
        self._save_user(user)
        return user

    def topup_user(self, user: UserRecord, amount: int) -> UserRecord:
        user.balance += amount
        self._save_user(user)
        return user

    # ── Task operations ────────────────────────────────────────────────

    def list_tasks(self) -> list[TaskPayload]:
        return list(self.tasks.values())

    def get_task(self, task_id: str) -> TaskPayload | None:
        return self.tasks.get(task_id)

    def list_tasks_for_agent(self, agent_id: str) -> list[TaskPayload]:
        return [t for t in self.tasks.values() if t.assigned_agent_id == agent_id]

    def list_user_tasks(self, user_id: str) -> list[TaskPayload]:
        return [t for t in self.tasks.values() if t.owner_user_id == user_id]

    def total_earned_for_agent(self, agent_id: str) -> int:
        return sum(e.amount for e in self.ledger_entries if e.agent_id == agent_id)

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
        self.clear_candidates_for_task(task_id)
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

    def update_progress(self, task_id: str, progress: int, message: str) -> dict | None:
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
        self, task_id: str, agent: AgentRecord, *, output, proof, stats,
    ) -> TaskPayload | None:
        task = self.tasks.get(task_id)
        if not task or task.assigned_agent_id != agent.agent_id:
            return None
        task.status = TaskStatus.submitted
        task.progress = 100
        task.settlement_state = SettlementState.pending_verification
        task.payment_state = PaymentState.awaiting_user_acceptance
        task.submission = TaskSubmission(
            output=output, proof=proof, stats=stats,
            submitted_at=utc_now(), submitted_by_agent_id=agent.agent_id,
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
        if (
            not task
            or task.owner_user_id != user.user_id
            or task.status not in {TaskStatus.submitted, TaskStatus.verified}
            or not task.assigned_agent_id
        ):
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
        entry = LedgerEntry(
            entry_id=f"led_{uuid4().hex[:12]}",
            agent_id=agent.agent_id,
            task_id=task.task_id,
            amount=task.reward,
            currency=task.currency,
            settlement_state=SettlementState.credited,
            note=note,
        )
        self.ledger_entries.append(entry)
        self._save_task(task)
        self._save_agent(agent)
        self._save_user(user)
        self._save_ledger_entry(entry)
        return task

    # ── Proposal operations ─────────────────────────────────────────────

    def submit_proposal(
        self, task_id: str, agent: AgentRecord, *, plan_steps, estimated_total_minutes, message,
    ) -> TaskProposal | None:
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.queued:
            return None
        # Prevent duplicate proposals from the same agent
        for p in self.proposals.values():
            if p.task_id == task_id and p.agent_id == agent.agent_id and p.status == ProposalStatus.pending:
                return None
        proposal = TaskProposal(
            proposal_id=f"prop_{uuid4().hex[:12]}",
            task_id=task_id,
            agent_id=agent.agent_id,
            agent_name=agent.registration.agent_name,
            plan_steps=plan_steps,
            estimated_total_minutes=estimated_total_minutes,
            message=message,
            status=ProposalStatus.pending,
            created_at=utc_now(),
        )
        self.proposals[proposal.proposal_id] = proposal
        self._save_proposal(proposal)
        return proposal

    def list_proposals_for_task(self, task_id: str) -> list[TaskProposal]:
        return [p for p in self.proposals.values() if p.task_id == task_id]

    def list_pending_proposals_for_task(self, task_id: str) -> list[TaskProposal]:
        return [
            p for p in self.proposals.values()
            if p.task_id == task_id and p.status == ProposalStatus.pending
        ]

    def get_proposal(self, proposal_id: str) -> TaskProposal | None:
        return self.proposals.get(proposal_id)

    def accept_proposal(self, proposal_id: str, user: UserRecord) -> TaskProposal | None:
        """User accepts a specific proposal → task assigned to that agent."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.status != ProposalStatus.pending:
            return None
        task = self.tasks.get(proposal.task_id)
        if not task or task.owner_user_id != user.user_id or task.status != TaskStatus.queued:
            return None
        agent = self.agents.get(proposal.agent_id)
        if not agent:
            return None
        # Accept this proposal
        proposal.status = ProposalStatus.accepted
        proposal.accepted_at = utc_now()
        self._save_proposal(proposal)
        # Reject all other pending proposals for this task
        for p in self.proposals.values():
            if p.task_id == proposal.task_id and p.proposal_id != proposal_id and p.status == ProposalStatus.pending:
                p.status = ProposalStatus.rejected
                self._save_proposal(p)
        # Assign task to the winning agent
        task.status = TaskStatus.assigned
        task.assigned_agent_id = agent.agent_id
        task.progress = 0
        task.settlement_state = None
        task.verification_note = None
        task.submission = None
        task.execution_plan = ExecutionPlan(
            summary=proposal.message or "Proposal accepted",
            steps=[s.title for s in proposal.plan_steps],
            estimated_duration_seconds=proposal.estimated_total_minutes * 60,
        )
        agent.current_load += 1
        self._save_task(task)
        self._save_agent(agent)
        self.clear_candidates_for_task(proposal.task_id)
        return proposal

    def reject_proposal(self, proposal_id: str, user: UserRecord) -> TaskProposal | None:
        """User rejects a specific proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.status != ProposalStatus.pending:
            return None
        task = self.tasks.get(proposal.task_id)
        if not task or task.owner_user_id != user.user_id:
            return None
        proposal.status = ProposalStatus.rejected
        self._save_proposal(proposal)
        return proposal

    def list_assigned_tasks_for_agent(self, agent_id: str) -> list[TaskPayload]:
        """Tasks confirmed by user and assigned to this agent, sorted by acceptance time (FIFO).

        Only includes tasks with status=assigned (not yet submitted).
        """
        assigned = [
            t for t in self.tasks.values()
            if t.assigned_agent_id == agent_id
            and t.status == TaskStatus.assigned
        ]
        # Sort by the proposal's accepted_at time (FIFO: oldest first)
        def _accepted_at(task: TaskPayload) -> str:
            for p in self.proposals.values():
                if p.task_id == task.task_id and p.agent_id == agent_id and p.status == ProposalStatus.accepted:
                    return p.accepted_at or ""
            return ""
        assigned.sort(key=_accepted_at)
        return assigned

    def update_step_progress(
        self, task_id: str, agent: AgentRecord, step_number: int, step_status: str, message: str,
    ) -> dict | None:
        """Agent reports progress on a specific step of the plan."""
        task = self.tasks.get(task_id)
        if not task or task.assigned_agent_id != agent.agent_id:
            return None
        # Find the accepted proposal to update step status
        proposal = None
        for p in self.proposals.values():
            if p.task_id == task_id and p.agent_id == agent.agent_id and p.status == ProposalStatus.accepted:
                proposal = p
                break
        if proposal:
            for step in proposal.plan_steps:
                if step.step_number == step_number:
                    step.status = step_status
                    break
            self._save_proposal(proposal)
            # Auto-calculate progress %
            total = len(proposal.plan_steps)
            completed = sum(1 for s in proposal.plan_steps if s.status in ("completed", "skipped"))
            in_progress = sum(1 for s in proposal.plan_steps if s.status == "in_progress")
            if total > 0:
                task.progress = min(100, int((completed * 100 + in_progress * 50) / total))
        else:
            # Fallback: no proposal found, just update progress as before
            pass
        # If first step starts, mark task as in_progress (keep assigned status but show activity)
        if step_status == "in_progress" and task.status == TaskStatus.assigned:
            pass  # keep assigned status, progress will show activity
        event = {
            "at": utc_now(),
            "step_number": step_number,
            "step_status": step_status,
            "progress": task.progress,
            "message": message,
        }
        self.progress_logs.setdefault(task_id, []).append(event)
        self._save_task(task)
        self._save_progress_event(task_id, event)
        return event

    def ledger_for_agent(self, agent_id: str) -> list[LedgerEntry]:
        return [e for e in self.ledger_entries if e.agent_id == agent_id]

    def list_ledger_entries(self) -> list[LedgerEntry]:
        return list(self.ledger_entries)

    # ── Uploaded files ──────────────────────────────────────────────────

    def _load_uploaded_files(self) -> None:
        for row in self._conn.execute("SELECT * FROM uploaded_files").fetchall():
            f = UploadedFile(
                file_id=row["file_id"],
                task_id=row["task_id"],
                agent_id=row["agent_id"],
                original_filename=row["original_filename"],
                content_type=row["content_type"],
                size_bytes=row["size_bytes"],
                download_url=row["download_url"],
                uploaded_at=row["uploaded_at"],
            )
            self.uploaded_files[f.file_id] = f

    def _save_uploaded_file(self, f: UploadedFile) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO uploaded_files
                   (file_id, task_id, agent_id, original_filename, content_type, size_bytes, download_url, uploaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f.file_id, f.task_id, f.agent_id, f.original_filename,
                 f.content_type, f.size_bytes, f.download_url, f.uploaded_at),
            )
            self._conn.commit()

    def save_uploaded_file(self, f: UploadedFile) -> None:
        self.uploaded_files[f.file_id] = f
        self._save_uploaded_file(f)

    def get_uploaded_file(self, file_id: str) -> UploadedFile | None:
        return self.uploaded_files.get(file_id)

    def list_files_for_task(self, task_id: str) -> list[UploadedFile]:
        return [f for f in self.uploaded_files.values() if f.task_id == task_id]


# ── Singleton accessor ─────────────────────────────────────────────────

_store_instance: SQLiteStore | None = None


def get_store() -> SQLiteStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = SQLiteStore()
    return _store_instance
