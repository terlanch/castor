from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_URL = os.getenv("CASTOR_BASE_URL", "https://postpneumonic-ungifted-gerry.ngrok-free.dev")
API_BASE = f"{BASE_URL.rstrip('/')}/api/v1"
CREDENTIALS_PATH = Path(
    os.getenv("CASTOR_CREDENTIALS_PATH", str(Path.home() / ".config" / "castor" / "credentials.json"))
)
STATE_PATH = Path(os.getenv("CASTOR_STATE_PATH", str(Path.home() / ".config" / "castor" / "worker-state.json")))
AGENT_NAME = os.getenv("CASTOR_AGENT_NAME", "OpenClaw-Agent")
AGENT_DESCRIPTION = os.getenv("CASTOR_AGENT_DESCRIPTION", "OpenClaw worker connected to Castor.")
HEARTBEAT_SECONDS = int(os.getenv("CASTOR_HEARTBEAT_SECONDS", "30"))
MAX_LOAD = int(os.getenv("CASTOR_AGENT_CONCURRENCY", "1"))
AUTO_ACCEPT = os.getenv("CASTOR_AUTO_ACCEPT", "false").lower() in {"1", "true", "yes", "on"}


def split_csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


AGENT_SKILLS = split_csv_env("CASTOR_AGENT_SKILLS", "research,planning")
AGENT_CATEGORIES = split_csv_env("CASTOR_AGENT_CATEGORIES", "solution_design,buyer_discovery")
AGENT_TOOLING = split_csv_env("CASTOR_AGENT_TOOLING", "browser,planner")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(f"{API_BASE}{path}", data=body, method=method, headers=headers)
    with request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def register_agent() -> dict[str, Any]:
    payload = {
        "agent_name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "mode": "polling",
        "skills": AGENT_SKILLS,
        "categories": AGENT_CATEGORIES,
        "concurrency": MAX_LOAD,
        "pricing": {},
        "region": os.getenv("CASTOR_AGENT_REGION", "global"),
        "tooling": AGENT_TOOLING,
        "compliance_flags": {
            "manual_review_supported": True,
            "restricted_domains_respected": True,
        },
        "metadata": {
            "runtime": "openclaw",
            "worker": "openclaw_castor_worker.py",
        },
    }
    result = api_request("POST", "/agents/register", payload=payload)
    credentials = {
        "api_key": result["agent"]["api_key"],
        "agent_id": result["agent"]["agent_id"],
        "agent_name": result["agent"]["username"],
        "profile_url": result["agent"]["profile_url"],
        "verification_code": result["agent"]["verification_code"],
    }
    write_json(CREDENTIALS_PATH, credentials)
    print(f"[castor-worker] registered agent {credentials['agent_name']} ({credentials['agent_id']})")
    return credentials


def load_credentials() -> dict[str, Any]:
    credentials = read_json(CREDENTIALS_PATH, {})
    required = {"api_key", "agent_id", "agent_name"}
    if not required.issubset(credentials):
        credentials = register_agent()
    return credentials


def load_state() -> dict[str, Any]:
    return read_json(
        STATE_PATH,
        {
            "active_task_id": None,
            "last_heartbeat_at": None,
            "last_polled_at": None,
            "seen_task_ids": [],
        },
    )


def save_state(state: dict[str, Any]) -> None:
    write_json(STATE_PATH, state)


def send_heartbeat(token: str, current_load: int) -> dict[str, Any]:
    payload = {
        "status": "busy" if current_load > 0 else "idle",
        "current_load": current_load,
        "max_load": MAX_LOAD,
        "healthy": True,
    }
    return api_request("POST", "/agents/heartbeat", token=token, payload=payload)


def poll_tasks(token: str) -> list[dict[str, Any]]:
    payload = {"categories": AGENT_CATEGORIES, "max_tasks": 3}
    result = api_request("POST", "/tasks/poll", token=token, payload=payload)
    return result.get("tasks", [])


def build_execution_plan(task: dict[str, Any]) -> dict[str, Any]:
    goal = task.get("goal") or task.get("title") or "Complete the assigned task."
    constraints = task.get("constraints") or []
    steps = [
        "Analyze task goal and acceptance criteria.",
        "Collect or generate the required information using local OpenClaw capabilities.",
        "Assemble the final deliverable and validate structure before submission.",
    ]
    if constraints:
        steps.insert(1, f"Respect task constraints: {', '.join(constraints[:3])}.")
    return {
        "summary": f"Plan for task: {goal}",
        "steps": steps,
        "estimated_duration_seconds": task.get("sla_seconds", 1800),
        "estimated_cost": task.get("reward"),
    }


def accept_task(token: str, task: dict[str, Any]) -> dict[str, Any]:
    payload = {"execution_plan": build_execution_plan(task)}
    return api_request("POST", f"/tasks/{task['task_id']}/accept", token=token, payload=payload)


def main() -> int:
    credentials = load_credentials()
    state = load_state()
    token = credentials["api_key"]
    print(f"[castor-worker] connected as {credentials['agent_name']}")
    print(f"[castor-worker] auto accept is {'enabled' if AUTO_ACCEPT else 'disabled'}")

    while True:
        try:
            current_load = 1 if state.get("active_task_id") else 0
            heartbeat = send_heartbeat(token, current_load)
            state["last_heartbeat_at"] = heartbeat.get("last_heartbeat_at")
            print(f"[castor-worker] heartbeat status={heartbeat.get('status')} load={current_load}")

            if current_load < MAX_LOAD:
                tasks = poll_tasks(token)
                state["last_polled_at"] = int(time.time())
                if tasks:
                    print(f"[castor-worker] polled {len(tasks)} task(s)")
                    for task in tasks:
                        print(f"  - {task['task_id']} | {task['title']}")
                    if AUTO_ACCEPT and not state.get("active_task_id"):
                        accepted = accept_task(token, tasks[0])
                        state["active_task_id"] = accepted["task"]["task_id"]
                        print(f"[castor-worker] accepted task {state['active_task_id']}")
                else:
                    print("[castor-worker] no tasks available")

            save_state(state)
            time.sleep(HEARTBEAT_SECONDS)
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            print(f"[castor-worker] http error {exc.code}: {message}", file=sys.stderr)
            if exc.code == 401:
                print("[castor-worker] credentials invalid, deleting local credentials and exiting", file=sys.stderr)
                if CREDENTIALS_PATH.exists():
                    CREDENTIALS_PATH.unlink()
                return 1
            time.sleep(HEARTBEAT_SECONDS)
        except Exception as exc:  # noqa: BLE001
            print(f"[castor-worker] unexpected error: {exc}", file=sys.stderr)
            time.sleep(HEARTBEAT_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
