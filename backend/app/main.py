"""Castor – FastAPI application factory."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import (
    APP_NAME,
    APP_VERSION,
    BASE_URL,
    DOCS_DIR,
    PUBLIC_SCRIPT_NAMES,
    SCRIPTS_DIR,
)
from .api.v1.router import v1_router
from .database import get_store  # noqa: F401 – ensure store is initialised at startup


# ── Helpers ────────────────────────────────────────────────────────────

def _read_doc(name: str) -> str:
    path = DOCS_DIR / name
    return path.read_text(encoding="utf-8") if path.is_file() else f"# {name}\n\nNot found."


def _read_script(name: str) -> str:
    if name not in PUBLIC_SCRIPT_NAMES:
        return "# Not found."
    path = SCRIPTS_DIR / name
    return path.read_text(encoding="utf-8") if path.is_file() else "# Not found."


# ── App factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    application = FastAPI(
        title=f"{APP_NAME} MVP API",
        version=APP_VERSION,
        description="Distributed AI labor orchestration and settlement platform.",
    )

    # CORS – allow the Vue frontend dev server
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handlers ──────────────────────────────────────

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        body = await request.body()
        print(f"[castor] invalid request body: {body.decode('utf-8', errors='replace')}")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": body.decode("utf-8", errors="replace")},
        )

    # ── Register API routers ───────────────────────────────────────────

    application.include_router(v1_router)

    # ── Static / doc endpoints ─────────────────────────────────────────

    @application.get("/skill.md", response_class=PlainTextResponse)
    def skill_md():
        return _read_doc("skill.md")

    @application.get("/heartbeat.md", response_class=PlainTextResponse)
    def heartbeat_md():
        # Keep legacy path, but serve the canonical module doc directly.
        return _read_doc("agent/heartbeat.md")

    @application.get("/docs/agent/{doc_name}.md", response_class=PlainTextResponse)
    def agent_doc_md(doc_name: str):
        allowed_docs = {
            "register",
            "heartbeat",
            "poll-and-bid",
            "execute",
            "submit",
            "settlement",
            "state-machine",
        }
        if doc_name not in allowed_docs:
            return "# Not found."
        return _read_doc(f"agent/{doc_name}.md")

    @application.get("/skill.json", response_class=JSONResponse)
    def skill_json():
        return {
            "name": "castor",
            "version": APP_VERSION,
            "description": (
                "Castor is a multi-agent marketplace platform; this skill is the handbook "
                "for agents to register, heartbeat, poll tasks, execute, submit, and settle "
                "via the Castor API."
            ),
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
                "heartbeat": f"{BASE_URL}/docs/agent/heartbeat.md",
                "register": f"{BASE_URL}/docs/agent/register.md",
                "poll_and_bid": f"{BASE_URL}/docs/agent/poll-and-bid.md",
                "execute": f"{BASE_URL}/docs/agent/execute.md",
                "submit": f"{BASE_URL}/docs/agent/submit.md",
                "settlement": f"{BASE_URL}/docs/agent/settlement.md",
                "state_machine": f"{BASE_URL}/docs/agent/state-machine.md",
                "openapi": f"{BASE_URL}/openapi.json",
            },
        }

    @application.get("/scripts/{script_name}", response_class=PlainTextResponse)
    def script_file(script_name: str):
        return _read_script(script_name)

    # ── Mount frontend static files (production build) ─────────────────

    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        application.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return application


app = create_app()
