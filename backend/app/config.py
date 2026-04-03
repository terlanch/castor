"""Castor platform – centralised configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
# backend/.env；不覆盖已在 shell / 系统中设置的同名变量
load_dotenv(BACKEND_DIR / ".env")
DATA_DIR = BACKEND_DIR / "data"
DOCS_DIR = BACKEND_DIR / "docs"
SCRIPTS_DIR = BACKEND_DIR / "scripts"
UPLOADS_DIR = DATA_DIR / "uploads"

# ── File upload limits ────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.getenv("CASTOR_MAX_UPLOAD_SIZE_MB", "100"))
ALLOWED_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".tgz", ".tar.gz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".tsv",
    ".txt", ".md", ".json", ".xml", ".yaml", ".yml",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".py", ".js", ".ts", ".html", ".css",
}

# ── App ────────────────────────────────────────────────────────────────
APP_NAME = "Castor"
APP_VERSION = "0.2.0"
BASE_URL = os.getenv(
    "CASTOR_BASE_URL",
    "http://localhost:8080",
)
FRONTEND_BASE_URL = os.getenv(
    "CASTOR_FRONTEND_BASE_URL",
    "http://localhost:3000",
)
ADMIN_TOKEN = os.getenv("CASTOR_ADMIN_TOKEN", "castor-admin")
HEARTBEAT_TIMEOUT_SECONDS = int(
    os.getenv("CASTOR_HEARTBEAT_TIMEOUT_SECONDS", "7200")
)

# ── Agent claim (OpenClaw creator onboarding) ─────────────────────────
# Shown in the verification tweet template; optional branding handle.
CASTOR_TWITTER_HANDLE = os.getenv("CASTOR_TWITTER_HANDLE", "castor")
CLAIM_EMAIL_VERIFY_TTL_MINUTES = int(
    os.getenv("CASTOR_CLAIM_EMAIL_VERIFY_TTL_MINUTES", "10")
)

# ── LLM (task understanding layer) ────────────────────────────────────
# CASTOR_LLM_API_KEY 优先；未设置时读取 ARK_API_KEY（与火山引擎文档一致）
LLM_API_KEY = os.getenv("CASTOR_LLM_API_KEY") or os.getenv("ARK_API_KEY", "")
LLM_BASE_URL = os.getenv("CASTOR_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("CASTOR_LLM_MODEL", "gpt-4o-mini")
# 设为 0 时不传 response_format（部分 OpenAI 兼容网关不支持 json_object）
LLM_JSON_OBJECT_MODE = os.getenv("CASTOR_LLM_JSON_OBJECT_MODE", "1") != "0"

# ── Database ───────────────────────────────────────────────────────────
DB_PATH = Path(os.getenv("CASTOR_DB_PATH", str(DATA_DIR / "castor.db")))

# ── Public scripts served to agents ────────────────────────────────────
PUBLIC_SCRIPT_NAMES = {
    "openclaw_castor_common.sh",
    "openclaw_castor_heartbeat.sh",
    "openclaw_castor_poll.sh",
    "openclaw_castor_tick.sh",
}
