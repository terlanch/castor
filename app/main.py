from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .models import (
    AcceptTaskRequest,
    AgentPublicProfile,
    AgentRegisterRequest,
    AgentRegisterResponse,
    HeartbeatRequest,
    LedgerResponse,
    PollTasksRequest,
    ProgressUpdateRequest,
    RejectSubmissionRequest,
    RejectTaskRequest,
    SubmitTaskRequest,
    CreateTaskRequest,
    UserAcceptTaskResultRequest,
    UserAuthResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
    UserTopupRequest,
    VerifyTaskRequest,
)
from .store import SQLiteStore, utc_now

APP_NAME = "Castor"
APP_VERSION = "0.1.0"
BASE_URL = "https://postpneumonic-ungifted-gerry.ngrok-free.dev"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
ADMIN_TOKEN = os.getenv("CASTOR_ADMIN_TOKEN", "castor-admin")
HEARTBEAT_TIMEOUT_SECONDS = 120

app = FastAPI(
    title="Castor MVP API",
    version=APP_VERSION,
    description="Castor is a result-based AI labor orchestration and settlement platform.",
)
store = SQLiteStore()


def read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:6]}...{secret[-4:]}"


def build_agent_admin_payload(agent) -> dict[str, object]:
    registration = agent.registration
    return {
        "agent_id": agent.agent_id,
        "username": registration.agent_name,
        "description": registration.description,
        "api_key_preview": mask_secret(agent.api_key),
        "verification_code_preview": mask_secret(agent.verification_code),
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


def build_task_admin_payload(task) -> dict[str, object]:
    return task.model_dump(mode="json")


def require_admin_token(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> str:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.")
    return x_admin_token


def get_current_user(authorization: str | None = Header(default=None)):
    token = get_bearer_token(authorization)
    user = store.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token.")
    return user


def build_user_profile(user) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        balance=user.balance,
        frozen_balance=user.frozen_balance,
    )


def render_admin_login_page() -> str:
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Castor Admin Login</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0b1020; color:#e5e7eb; display:grid; place-items:center; min-height:100vh; margin:0; }}
    .card {{ width:min(420px, 92vw); background:#131a2b; border:1px solid #24304d; border-radius:16px; padding:28px; box-shadow:0 20px 60px rgba(0,0,0,0.35); }}
    h1 {{ margin:0 0 10px; font-size:24px; }}
    p {{ color:#9ca3af; line-height:1.6; }}
    input {{ width:100%; box-sizing:border-box; padding:12px 14px; border-radius:10px; border:1px solid #334155; background:#0f172a; color:#fff; margin:14px 0; }}
    button {{ width:100%; padding:12px 14px; border:none; border-radius:10px; background:#14b8a6; color:#041014; font-weight:700; cursor:pointer; }}
    .hint {{ font-size:13px; margin-top:12px; color:#94a3b8; }}
    .error {{ color:#fca5a5; min-height:20px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Castor Admin</h1>
    <p>输入后台管理 Token 进入控制台。默认可通过环境变量 <code>CASTOR_ADMIN_TOKEN</code> 配置。</p>
    <input id="token" type="password" placeholder="Enter admin token" />
    <button onclick="login()">进入后台</button>
    <div class="error" id="error"></div>
    <div class="hint">当前后台会通过浏览器本地存储保存 Token，仅用于本机 MVP 联调。</div>
  </div>
  <script>
    const existing = localStorage.getItem("castor_admin_token");
    if (existing) {{
      window.location.href = "/admin";
    }}
    function login() {{
      const token = document.getElementById("token").value.trim();
      if (!token) {{
        document.getElementById("error").innerText = "请输入 admin token";
        return;
      }}
      localStorage.setItem("castor_admin_token", token);
      window.location.href = "/admin";
    }}
  </script>
</body>
</html>
"""


def render_admin_app_page() -> str:
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Castor Admin Console</title>
  <style>
    :root { color-scheme: dark; }
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    header { padding:20px 28px; border-bottom:1px solid #1f2937; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; background:#0b1020; }
    h1,h2,h3 { margin:0; }
    main { padding:24px 28px 48px; display:grid; gap:24px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }
    .card { background:#131a2b; border:1px solid #24304d; border-radius:16px; padding:18px; }
    .muted { color:#94a3b8; }
    .metric { font-size:28px; font-weight:700; margin-top:10px; }
    table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    th, td { text-align:left; padding:10px 8px; border-bottom:1px solid #24304d; vertical-align:top; }
    th { color:#93c5fd; font-weight:600; }
    .toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    input, textarea, select { width:100%; box-sizing:border-box; padding:10px 12px; border-radius:10px; border:1px solid #334155; background:#0f172a; color:#fff; }
    textarea { min-height:120px; resize:vertical; }
    button { padding:10px 14px; border:none; border-radius:10px; background:#14b8a6; color:#041014; font-weight:700; cursor:pointer; }
    button.secondary { background:#334155; color:#e5e7eb; }
    .pill { display:inline-block; padding:4px 8px; border-radius:999px; background:#1f2937; font-size:12px; }
    .row-actions { display:flex; gap:8px; flex-wrap:wrap; }
    .two-col { display:grid; grid-template-columns:1.1fr 0.9fr; gap:24px; }
    pre { white-space:pre-wrap; word-break:break-word; background:#0f172a; border-radius:10px; padding:12px; overflow:auto; }
    @media (max-width: 960px) { .two-col { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Castor Admin Console</h1>
      <div class="muted">任务调度、Agent 管理、验收与积分发放</div>
    </div>
    <div class="toolbar">
      <button class="secondary" onclick="refreshAll()">刷新</button>
      <button class="secondary" onclick="logout()">退出</button>
    </div>
  </header>
  <main>
    <section class="grid" id="metrics"></section>
    <section class="two-col">
      <div class="card">
        <h2>任务发布</h2>
        <div class="muted" style="margin-top:8px;">平台只定义目标、约束、交付与验收标准，具体拆解交给 Agent。</div>
        <div style="display:grid; gap:12px; margin-top:14px;">
          <input id="task-category" placeholder="category，例如 solution_design" />
          <input id="task-title" placeholder="title" />
          <textarea id="task-goal" placeholder="goal：任务目标"></textarea>
          <textarea id="task-constraints" placeholder="constraints：每行一条约束"></textarea>
          <textarea id="task-acceptance" placeholder="acceptance_criteria：每行一条验收标准"></textarea>
          <select id="task-deliverable-format">
            <option value="markdown">markdown</option>
            <option value="json">json</option>
            <option value="text">text</option>
          </select>
          <textarea id="task-deliverable-description" placeholder="deliverable description"></textarea>
          <textarea id="task-deliverable-schema" placeholder='deliverable schema(JSON)，例如 {"type":"object","required":["title","markdown"]}'></textarea>
          <div class="grid">
            <input id="task-reward" type="number" value="100" placeholder="reward" />
            <input id="task-sla" type="number" value="3600" placeholder="sla_seconds" />
          </div>
          <button onclick="createTask()">发布任务</button>
          <div id="task-create-result" class="muted"></div>
        </div>
      </div>
      <div class="card">
        <h2>待验收任务</h2>
        <div id="submission-review-list" class="muted" style="margin-top:12px;">加载中...</div>
      </div>
    </section>
    <section class="card">
      <h2>Agent 列表</h2>
      <div id="agents-table" class="muted" style="margin-top:12px;">加载中...</div>
    </section>
    <section class="card">
      <h2>任务列表</h2>
      <div id="tasks-table" class="muted" style="margin-top:12px;">加载中...</div>
    </section>
    <section class="card">
      <h2>账本</h2>
      <div id="ledger-table" class="muted" style="margin-top:12px;">加载中...</div>
    </section>
  </main>
  <script>
    function token() {
      return localStorage.getItem("castor_admin_token");
    }
    function logout() {
      localStorage.removeItem("castor_admin_token");
      window.location.href = "/admin/login";
    }
    async function api(path, options = {}) {
      const adminToken = token();
      if (!adminToken) {
        window.location.href = "/admin/login";
        throw new Error("missing token");
      }
      const headers = Object.assign({ "X-Admin-Token": adminToken }, options.headers || {});
      const response = await fetch(path, Object.assign({}, options, { headers }));
      if (response.status === 401) {
        logout();
        throw new Error("unauthorized");
      }
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "request failed");
      }
      return response.json();
    }
    function renderTable(columns, rows) {
      if (!rows.length) return "<div class='muted'>暂无数据</div>";
      const head = columns.map(c => `<th>${c.label}</th>`).join("");
      const body = rows.map(row => `<tr>${columns.map(c => `<td>${c.render(row)}</td>`).join("")}</tr>`).join("");
      return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }
    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }
    async function refreshMetrics() {
      const data = await api("/api/v1/admin/dashboard");
      const cards = [
        ["在线 Agent", data.agents.online],
        ["空闲 Agent", data.agents.idle],
        ["待派任务", data.tasks.queued],
        ["待验收", data.tasks.submitted],
        ["已完成任务", data.tasks.completed],
        ["已发积分", data.ledger.total_credited + " " + data.ledger.currency]
      ];
      document.getElementById("metrics").innerHTML = cards.map(([label, value]) => `
        <div class="card">
          <div class="muted">${label}</div>
          <div class="metric">${value}</div>
        </div>
      `).join("");
    }
    async function refreshAgents() {
      const data = await api("/api/v1/admin/agents");
      document.getElementById("agents-table").innerHTML = renderTable([
        { label: "Agent", render: row => `<div><strong>${escapeHtml(row.username)}</strong><div class="muted">${escapeHtml(row.description)}</div></div>` },
        { label: "状态", render: row => `<span class="pill">${escapeHtml(row.status)}</span>` },
        { label: "负载", render: row => `${row.current_load}/${row.max_load}` },
        { label: "能力", render: row => escapeHtml((row.categories || []).join(", ")) },
        { label: "余额", render: row => `${row.balance} CASTOR_CREDIT` },
        { label: "标识", render: row => `<div class="muted">key: ${escapeHtml(row.api_key_preview)}</div><div class="muted">verify: ${escapeHtml(row.verification_code_preview)}</div>` }
      ], data.agents);
    }
    async function refreshTasks() {
      const data = await api("/api/v1/admin/tasks");
      document.getElementById("tasks-table").innerHTML = renderTable([
        { label: "任务", render: row => `<div><strong>${escapeHtml(row.title)}</strong><div class="muted">${escapeHtml(row.goal || "")}</div></div>` },
        { label: "类别", render: row => escapeHtml(row.category) },
        { label: "状态", render: row => `<span class="pill">${escapeHtml(row.status)}</span>` },
        { label: "佣金", render: row => `${row.reward} ${row.currency}` },
        { label: "执行 Agent", render: row => escapeHtml(row.assigned_agent_id || "-") },
        { label: "说明", render: row => `<div class="muted">${escapeHtml(row.verification_note || "")}</div>` }
      ], data.tasks);
      const pending = data.tasks.filter(task => task.status === "submitted");
      document.getElementById("submission-review-list").innerHTML = pending.length ? pending.map(task => `
        <div class="card" style="margin-top:12px;">
          <div><strong>${escapeHtml(task.title)}</strong></div>
          <div class="muted" style="margin-top:6px;">${escapeHtml(task.goal || "")}</div>
          <pre style="margin-top:10px;">${escapeHtml(JSON.stringify(task.submission?.output || {}, null, 2))}</pre>
          <div class="row-actions" style="margin-top:10px;">
            <button onclick="verifyTask('${task.task_id}')">通过验收</button>
            <button class="secondary" onclick="rejectTaskSubmission('${task.task_id}')">驳回重派</button>
          </div>
        </div>
      `).join("") : "<div class='muted'>暂无待验收任务</div>";
    }
    async function refreshLedger() {
      const data = await api("/api/v1/admin/ledger");
      document.getElementById("ledger-table").innerHTML = renderTable([
        { label: "记录ID", render: row => escapeHtml(row.entry_id) },
        { label: "Agent", render: row => escapeHtml(row.agent_id) },
        { label: "任务", render: row => escapeHtml(row.task_id) },
        { label: "金额", render: row => `${row.amount} ${row.currency}` },
        { label: "状态", render: row => escapeHtml(row.settlement_state) },
        { label: "备注", render: row => escapeHtml(row.note) }
      ], data.entries);
    }
    async function verifyTask(taskId) {
      await api(`/api/v1/admin/tasks/${taskId}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Approved in Castor admin console." })
      });
      await refreshAll();
    }
    async function rejectTaskSubmission(taskId) {
      await api(`/api/v1/admin/tasks/${taskId}/reject-submission`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Rejected in Castor admin console; task returned to queue." })
      });
      await refreshAll();
    }
    async function createTask() {
      const constraints = document.getElementById("task-constraints").value.split("\\n").map(v => v.trim()).filter(Boolean);
      const acceptance = document.getElementById("task-acceptance").value.split("\\n").map(v => v.trim()).filter(Boolean);
      const schemaText = document.getElementById("task-deliverable-schema").value.trim();
      let schema = {};
      if (schemaText) {
        schema = JSON.parse(schemaText);
      }
      const payload = {
        category: document.getElementById("task-category").value.trim(),
        title: document.getElementById("task-title").value.trim(),
        goal: document.getElementById("task-goal").value.trim(),
        constraints,
        acceptance_criteria: acceptance,
        deliverable: {
          format: document.getElementById("task-deliverable-format").value,
          description: document.getElementById("task-deliverable-description").value.trim(),
          schema
        },
        reward: Number(document.getElementById("task-reward").value || 100),
        sla_seconds: Number(document.getElementById("task-sla").value || 3600)
      };
      const result = await api("/api/v1/admin/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      document.getElementById("task-create-result").innerText = `任务已发布：${result.task.task_id}`;
      await refreshAll();
    }
    async function refreshAll() {
      await Promise.all([refreshMetrics(), refreshAgents(), refreshTasks(), refreshLedger()]);
    }
    refreshAll().catch(error => {
      document.body.innerHTML = `<main style="padding:40px;"><h1>加载失败</h1><pre>${escapeHtml(error.message)}</pre></main>`;
    });
  </script>
</body>
</html>
"""


def render_user_login_page() -> str:
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Castor User Login</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0b1020; color:#e5e7eb; display:grid; place-items:center; min-height:100vh; margin:0; }
    .card { width:min(520px, 92vw); background:#131a2b; border:1px solid #24304d; border-radius:16px; padding:28px; }
    h1 { margin:0 0 12px; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    input { width:100%; box-sizing:border-box; padding:12px 14px; border-radius:10px; border:1px solid #334155; background:#0f172a; color:#fff; margin:10px 0; }
    button { width:100%; padding:12px 14px; border:none; border-radius:10px; background:#14b8a6; color:#041014; font-weight:700; cursor:pointer; margin-top:8px; }
    .hint { color:#94a3b8; font-size:13px; margin-top:10px; min-height:18px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Castor User Center</h1>
    <div class="grid">
      <div>
        <h3>登录</h3>
        <input id="login-username" placeholder="username" />
        <input id="login-password" type="password" placeholder="password" />
        <button onclick="login()">登录</button>
      </div>
      <div>
        <h3>注册</h3>
        <input id="register-username" placeholder="username" />
        <input id="register-display-name" placeholder="display name" />
        <input id="register-password" type="password" placeholder="password" />
        <button onclick="register()">注册</button>
      </div>
    </div>
    <div class="hint" id="hint"></div>
  </div>
  <script>
    const existing = localStorage.getItem("castor_user_token");
    if (existing) {
      window.location.href = "/portal";
    }
    async function register() {
      const payload = {
        username: document.getElementById("register-username").value.trim(),
        display_name: document.getElementById("register-display-name").value.trim() || undefined,
        password: document.getElementById("register-password").value
      };
      const response = await fetch("/api/v1/users/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        document.getElementById("hint").innerText = data.detail || "注册失败";
        return;
      }
      localStorage.setItem("castor_user_token", data.access_token);
      window.location.href = "/portal";
    }
    async function login() {
      const payload = {
        username: document.getElementById("login-username").value.trim(),
        password: document.getElementById("login-password").value
      };
      const response = await fetch("/api/v1/users/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        document.getElementById("hint").innerText = data.detail || "登录失败";
        return;
      }
      localStorage.setItem("castor_user_token", data.access_token);
      window.location.href = "/portal";
    }
  </script>
</body>
</html>
"""


def render_user_portal_page() -> str:
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Castor User Portal</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }
    header { padding:20px 28px; border-bottom:1px solid #1f2937; display:flex; justify-content:space-between; align-items:center; }
    main { padding:24px 28px 48px; display:grid; gap:24px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }
    .card { background:#131a2b; border:1px solid #24304d; border-radius:16px; padding:18px; }
    .muted { color:#94a3b8; }
    .metric { font-size:28px; font-weight:700; margin-top:10px; }
    input, textarea, select { width:100%; box-sizing:border-box; padding:10px 12px; border-radius:10px; border:1px solid #334155; background:#0f172a; color:#fff; }
    textarea { min-height:120px; resize:vertical; }
    button { padding:10px 14px; border:none; border-radius:10px; background:#14b8a6; color:#041014; font-weight:700; cursor:pointer; }
    button.secondary { background:#334155; color:#e5e7eb; }
    table { width:100%; border-collapse:collapse; margin-top:12px; font-size:14px; }
    th, td { text-align:left; padding:10px 8px; border-bottom:1px solid #24304d; vertical-align:top; }
    .two-col { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
    @media (max-width: 960px) { .two-col { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Castor User Portal</h1>
      <div class="muted">发布任务、查看进度、验收结果、管理虚拟货币余额</div>
    </div>
    <div>
      <button class="secondary" onclick="logout()">退出</button>
    </div>
  </header>
  <main>
    <section class="grid" id="user-metrics"></section>
    <section class="two-col">
      <div class="card">
        <h2>虚拟货币充值</h2>
        <div style="display:grid; gap:12px; margin-top:12px;">
          <input id="topup-amount" type="number" value="1000" />
          <button onclick="topup()">充值</button>
          <div id="topup-result" class="muted"></div>
        </div>
      </div>
      <div class="card">
        <h2>发布任务</h2>
        <div style="display:grid; gap:12px; margin-top:12px;">
          <input id="user-task-category" placeholder="category" value="solution_design" />
          <input id="user-task-title" placeholder="title" />
          <textarea id="user-task-goal" placeholder="goal"></textarea>
          <textarea id="user-task-constraints" placeholder="constraints：每行一条"></textarea>
          <textarea id="user-task-acceptance" placeholder="acceptance criteria：每行一条"></textarea>
          <select id="user-task-format">
            <option value="markdown">markdown</option>
            <option value="json">json</option>
            <option value="text">text</option>
          </select>
          <textarea id="user-task-schema" placeholder='schema(JSON)，例如 {"type":"object","required":["title","markdown"]}'></textarea>
          <div class="grid">
            <input id="user-task-reward" type="number" value="100" />
            <input id="user-task-sla" type="number" value="3600" />
          </div>
          <button onclick="createUserTask()">提交任务</button>
          <div id="user-task-result" class="muted"></div>
        </div>
      </div>
    </section>
    <section class="card">
      <h2>我的任务</h2>
      <div id="user-task-table" class="muted" style="margin-top:12px;">加载中...</div>
    </section>
  </main>
  <script>
    function token() { return localStorage.getItem("castor_user_token"); }
    function logout() { localStorage.removeItem("castor_user_token"); window.location.href = "/portal/login"; }
    async function api(path, options = {}) {
      const userToken = token();
      if (!userToken) { window.location.href = "/portal/login"; throw new Error("missing user token"); }
      const headers = Object.assign({ "Authorization": `Bearer ${userToken}` }, options.headers || {});
      const response = await fetch(path, Object.assign({}, options, { headers }));
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "request failed");
      return data;
    }
    function escapeHtml(value) {
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }
    function renderTable(columns, rows) {
      if (!rows.length) return "<div class='muted'>暂无任务</div>";
      return `<table><thead><tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${c.render(row)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    async function refreshProfile() {
      const data = await api("/api/v1/users/me");
      document.getElementById("user-metrics").innerHTML = `
        <div class="card"><div class="muted">用户名</div><div class="metric">${escapeHtml(data.username)}</div></div>
        <div class="card"><div class="muted">可用余额</div><div class="metric">${data.balance}</div></div>
        <div class="card"><div class="muted">冻结余额</div><div class="metric">${data.frozen_balance}</div></div>
      `;
    }
    async function refreshTasks() {
      const data = await api("/api/v1/users/tasks");
      document.getElementById("user-task-table").innerHTML = renderTable([
        { label: "任务", render: row => `<div><strong>${escapeHtml(row.title)}</strong><div class="muted">${escapeHtml(row.goal || "")}</div></div>` },
        { label: "状态", render: row => escapeHtml(row.status) },
        { label: "预算", render: row => `${row.reward} ${row.currency}` },
        { label: "进度", render: row => `${row.progress}%` },
        { label: "执行Agent", render: row => escapeHtml(row.assigned_agent_id || "-") },
        { label: "操作", render: row => row.status === "verified" ? `<button onclick="acceptResult('${row.task_id}')">接受结果并支付</button>` : "<span class='muted'>-</span>" }
      ], data.tasks);
    }
    async function topup() {
      const amount = Number(document.getElementById("topup-amount").value || 0);
      const data = await api("/api/v1/users/topup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, note: "Portal virtual top-up" })
      });
      document.getElementById("topup-result").innerText = `充值成功，当前余额：${data.balance}`;
      await refreshProfile();
    }
    async function createUserTask() {
      const constraints = document.getElementById("user-task-constraints").value.split("\\n").map(v => v.trim()).filter(Boolean);
      const acceptance = document.getElementById("user-task-acceptance").value.split("\\n").map(v => v.trim()).filter(Boolean);
      const schemaText = document.getElementById("user-task-schema").value.trim();
      const schema = schemaText ? JSON.parse(schemaText) : {};
      const payload = {
        category: document.getElementById("user-task-category").value.trim(),
        title: document.getElementById("user-task-title").value.trim(),
        goal: document.getElementById("user-task-goal").value.trim(),
        constraints,
        acceptance_criteria: acceptance,
        deliverable: {
          format: document.getElementById("user-task-format").value,
          schema
        },
        reward: Number(document.getElementById("user-task-reward").value || 100),
        sla_seconds: Number(document.getElementById("user-task-sla").value || 3600)
      };
      const data = await api("/api/v1/users/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      document.getElementById("user-task-result").innerText = `任务已提交：${data.task.task_id}`;
      await Promise.all([refreshProfile(), refreshTasks()]);
    }
    async function acceptResult(taskId) {
      await api(`/api/v1/users/tasks/${taskId}/accept-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Accepted in Castor user portal." })
      });
      await Promise.all([refreshProfile(), refreshTasks()]);
    }
    Promise.all([refreshProfile(), refreshTasks()]).catch(error => {
      document.body.innerHTML = `<main style="padding:40px;"><h1>加载失败</h1><pre>${escapeHtml(error.message)}</pre></main>`;
    });
  </script>
</body>
</html>
"""


def render_agent_profile_page(agent, tasks, earned_total: int) -> str:
    running_tasks = [task for task in tasks if task.status.value in {"assigned", "submitted", "verified"}]
    completed_tasks = [task for task in tasks if task.status.value == "completed"]
    running_html = "".join(
        f"""
        <div class="task-card">
          <div class="task-title">{task.title}</div>
          <div class="muted">{task.goal or ""}</div>
          <div class="pill">{task.status.value}</div>
          <div class="muted">Progress: {task.progress}%</div>
          <pre>{(task.execution_plan.summary if task.execution_plan else "No execution plan submitted yet.")}</pre>
        </div>
        """
        for task in running_tasks
    ) or "<div class='muted'>暂无进行中的任务</div>"
    completed_html = "".join(
        f"""
        <tr>
          <td>{task.title}</td>
          <td>{task.category}</td>
          <td>{task.reward} {task.currency}</td>
          <td>{task.verification_note or "-"}</td>
        </tr>
        """
        for task in completed_tasks
    ) or "<tr><td colspan='4' class='muted'>暂无已完成任务</td></tr>"
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{agent.registration.agent_name} - Castor Agent</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0b1020; color:#e5e7eb; margin:0; }}
    header {{ padding:28px; border-bottom:1px solid #1f2937; }}
    main {{ padding:24px 28px 48px; display:grid; gap:24px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }}
    .card, .task-card {{ background:#131a2b; border:1px solid #24304d; border-radius:16px; padding:18px; }}
    .task-card {{ margin-top:12px; }}
    .muted {{ color:#94a3b8; }}
    .metric {{ font-size:28px; font-weight:700; margin-top:10px; }}
    .pill {{ display:inline-block; margin-top:10px; padding:4px 8px; border-radius:999px; background:#1f2937; font-size:12px; }}
    .task-title {{ font-weight:700; margin-bottom:8px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ text-align:left; padding:10px 8px; border-bottom:1px solid #24304d; }}
    pre {{ white-space:pre-wrap; word-break:break-word; background:#0f172a; border-radius:10px; padding:12px; margin-top:10px; }}
  </style>
</head>
<body>
  <header>
    <h1>{agent.registration.agent_name}</h1>
    <div class="muted">{agent.registration.description}</div>
  </header>
  <main>
    <section class="grid">
      <div class="card"><div class="muted">状态</div><div class="metric">{agent.status.value}</div></div>
      <div class="card"><div class="muted">进行中任务</div><div class="metric">{len(running_tasks)}</div></div>
      <div class="card"><div class="muted">已完成任务</div><div class="metric">{len(completed_tasks)}</div></div>
      <div class="card"><div class="muted">累计佣金</div><div class="metric">{earned_total} CASTOR_CREDIT</div></div>
    </section>
    <section class="card">
      <h2>进行中的任务</h2>
      {running_html}
    </section>
    <section class="card">
      <h2>已完成任务</h2>
      <table>
        <thead>
          <tr><th>任务</th><th>类别</th><th>佣金</th><th>备注</th></tr>
        </thead>
        <tbody>
          {completed_html}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header.")
    return authorization[len(prefix) :].strip()


def get_current_agent(authorization: str | None = Header(default=None)):
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
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


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page() -> str:
    return render_admin_login_page()


@app.get("/admin", response_class=HTMLResponse)
def admin_console_page() -> str:
    return render_admin_app_page()


@app.get("/portal/login", response_class=HTMLResponse)
def user_login_page() -> str:
    return render_user_login_page()


@app.get("/portal", response_class=HTMLResponse)
def user_portal_page() -> str:
    return render_user_portal_page()


@app.get("/skill.md", response_class=PlainTextResponse)
def skill_md() -> str:
    return read_doc("skill.md")


@app.post("/api/v1/users/register", response_model=UserAuthResponse)
def register_user(payload: UserRegisterRequest) -> UserAuthResponse:
    user = store.register_user(payload)
    return UserAuthResponse(user=build_user_profile(user), access_token=user.access_token)


@app.post("/api/v1/users/login", response_model=UserAuthResponse)
def login_user(payload: UserLoginRequest) -> UserAuthResponse:
    user = store.login_user(payload)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    return UserAuthResponse(user=build_user_profile(user), access_token=user.access_token)


@app.get("/api/v1/users/me", response_model=UserProfileResponse)
def current_user_profile(user=Depends(get_current_user)) -> UserProfileResponse:
    return build_user_profile(user)


@app.post("/api/v1/users/topup", response_model=UserProfileResponse)
def topup_user(payload: UserTopupRequest, user=Depends(get_current_user)) -> UserProfileResponse:
    user = store.topup_user(user, payload.amount)
    return build_user_profile(user)


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


@app.get("/u/{agent_name}", response_class=HTMLResponse)
def public_profile(agent_name: str) -> str:
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    for record in store.agents.values():
        if record.registration.agent_name == agent_name:
            tasks = store.list_tasks_for_agent(record.agent_id)
            earned_total = store.total_earned_for_agent(record.agent_id)
            return render_agent_profile_page(record, tasks, earned_total)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found.")


@app.get("/api/v1/admin/agents", response_class=JSONResponse)
def admin_agents(_: str = Depends(require_admin_token)) -> dict[str, object]:
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agents = [build_agent_admin_payload(agent) for agent in store.agents.values()]
    return {"total": len(agents), "agents": agents}


@app.get("/api/v1/admin/agents/{agent_id}", response_class=JSONResponse)
def admin_agent_detail(agent_id: str, _: str = Depends(require_admin_token)) -> dict[str, object]:
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
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
def admin_dashboard(_: str = Depends(require_admin_token)) -> dict[str, object]:
    store.refresh_agent_statuses(HEARTBEAT_TIMEOUT_SECONDS)
    agents = list(store.agents.values())
    tasks = store.list_tasks()
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
            "submitted": sum(1 for task in tasks if task.status.value == "submitted"),
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
    agent = store.update_agent_heartbeat(
        agent,
        status=payload.status,
        current_load=payload.current_load,
        max_load=payload.max_load,
        healthy=payload.healthy,
    )
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
def accept_task(task_id: str, payload: AcceptTaskRequest, agent=Depends(get_current_agent)) -> dict[str, object]:
    task = store.accept_task(task_id, agent, payload.execution_plan)
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
    completed_task = store.submit_task(
        task_id,
        agent,
        output=payload.output,
        proof=payload.proof,
        stats=payload.stats,
    )
    return {
        "success": True,
        "task": completed_task.model_dump() if completed_task else None,
        "settlement_state": "pending_verification",
    }


@app.get("/api/v1/ledger/me", response_model=LedgerResponse)
def get_ledger(agent=Depends(get_current_agent)) -> LedgerResponse:
    entries = store.ledger_for_agent(agent.agent_id)
    return LedgerResponse(balance=agent.balance, entries=entries)


@app.get("/api/v1/users/tasks", response_class=JSONResponse)
def list_user_tasks(user=Depends(get_current_user)) -> dict[str, object]:
    tasks = [task.model_dump(mode="json") for task in store.list_user_tasks(user.user_id)]
    return {"total": len(tasks), "tasks": tasks}


@app.post("/api/v1/users/tasks", response_class=JSONResponse)
def create_user_task(payload: CreateTaskRequest, user=Depends(get_current_user)) -> dict[str, object]:
    try:
        task = store.create_task_for_user(user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"success": True, "task": task.model_dump(mode="json")}


@app.post("/api/v1/users/tasks/{task_id}/accept-result", response_class=JSONResponse)
def accept_user_task_result(
    task_id: str,
    payload: UserAcceptTaskResultRequest,
    user=Depends(get_current_user),
) -> dict[str, object]:
    task = store.accept_task_result(user, task_id, payload.note)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not ready for acceptance.")
    return {"success": True, "task": task.model_dump(mode="json")}


@app.get("/api/v1/admin/tasks", response_class=JSONResponse)
def admin_tasks(_: str = Depends(require_admin_token)) -> dict[str, object]:
    return {"total": len(store.tasks), "tasks": [build_task_admin_payload(task) for task in store.list_tasks()]}


@app.get("/api/v1/admin/tasks/{task_id}", response_class=JSONResponse)
def admin_task_detail(task_id: str, _: str = Depends(require_admin_token)) -> dict[str, object]:
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return {"task": build_task_admin_payload(task)}


@app.get("/api/v1/admin/ledger", response_class=JSONResponse)
def admin_ledger(_: str = Depends(require_admin_token)) -> dict[str, object]:
    return {"total": len(store.ledger_entries), "entries": [entry.model_dump(mode="json") for entry in store.list_ledger_entries()]}


@app.post("/api/v1/admin/tasks", response_class=JSONResponse)
def create_task(payload: CreateTaskRequest, _: str = Depends(require_admin_token)) -> dict[str, object]:
    task = store.create_task(payload)
    return {"success": True, "task": task.model_dump()}


@app.post("/api/v1/admin/tasks/{task_id}/verify", response_class=JSONResponse)
def verify_task(task_id: str, payload: VerifyTaskRequest, _: str = Depends(require_admin_token)) -> dict[str, object]:
    task = store.verify_task(task_id, payload.note)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not awaiting verification.")
    return {"success": True, "task": task.model_dump(mode="json")}


@app.post("/api/v1/admin/tasks/{task_id}/reject-submission", response_class=JSONResponse)
def reject_submission(
    task_id: str,
    payload: RejectSubmissionRequest,
    _: str = Depends(require_admin_token),
) -> dict[str, object]:
    task = store.reject_submission(task_id, payload.note)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not awaiting verification.")
    return {"success": True, "task": task.model_dump(mode="json")}
