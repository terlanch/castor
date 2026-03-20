"""Castor platform – centralised configuration."""
from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
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

# ── LLM (task understanding layer) ────────────────────────────────────
LLM_API_KEY = os.getenv("CASTOR_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("CASTOR_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("CASTOR_LLM_MODEL", "gpt-4o-mini")

# ── Database ───────────────────────────────────────────────────────────
DB_PATH = Path(os.getenv("CASTOR_DB_PATH", str(DATA_DIR / "castor.db")))

# ── Public scripts served to agents ────────────────────────────────────
PUBLIC_SCRIPT_NAMES = {
    "openclaw_castor_common.sh",
    "openclaw_castor_heartbeat.sh",
    "openclaw_castor_poll.sh",
    "openclaw_castor_tick.sh",
}
