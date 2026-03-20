"""Task HTTP endpoints (Agent-facing).

Workflow:
  1. POST /tasks/poll          — poll recommended tasks
  2. POST /tasks/{id}/propose  — submit a structured proposal
     ↓ waiting for user confirmation ↓
  3. GET  /tasks/next          — get the next task to execute (at most one)
  4. POST /tasks/{id}/step-progress — report step progress
  5. POST /tasks/{id}/upload   — upload result files
  6. POST /tasks/{id}/submit   — submit the final result
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

import json

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import JSONResponse

from ....common.deps import get_current_agent
from ....config import BASE_URL, MAX_UPLOAD_SIZE_MB, UPLOADS_DIR, ALLOWED_EXTENSIONS
from ....database import get_store
from .schema import (
    PollTasksRequest,
    ProgressUpdateRequest,
    StepProgressRequest,
    SubmitProposalRequest,
    SubmitTaskRequest,
    UploadedFile as UploadedFileMeta,
)
from . import service

router = APIRouter(prefix="/tasks", tags=["Task"])


def _save_uploaded_file(task_id: str, agent_id: str, file: UploadFile) -> UploadedFileMeta:
    """Persist one uploaded file and return its metadata."""
    # Validate filename / extension
    original = file.filename or "unnamed"
    suffix = Path(original).suffix.lower()
    if original.lower().endswith(".tar.gz"):
        suffix = ".tar.gz"
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{suffix}' not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Read content with size limit
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = file.file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(content)/(1024*1024):.1f} MB). Max: {MAX_UPLOAD_SIZE_MB} MB.",
        )

    file_id = str(uuid4())
    task_dir = UPLOADS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    disk_name = f"{file_id}{suffix}"
    disk_path = task_dir / disk_name
    disk_path.write_bytes(content)

    content_type = file.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream"
    download_url = f"{BASE_URL}/api/v1/files/{file_id}"

    from ....database import utc_now
    meta = UploadedFileMeta(
        file_id=file_id,
        task_id=task_id,
        agent_id=agent_id,
        original_filename=original,
        content_type=content_type,
        size_bytes=len(content),
        download_url=download_url,
        uploaded_at=utc_now(),
    )
    get_store().save_uploaded_file(meta)
    print(f"[castor] file uploaded: {original} ({len(content)} bytes) -> {download_url}")
    return meta


# ── 1. Browse / Poll ─────────────────────────────────────────────────

@router.post("/poll", response_class=JSONResponse)
def poll_tasks(payload: PollTasksRequest, agent=Depends(get_current_agent)):
    """Poll available tasks that match the agent's profile.

    Returns full task details + match metadata (score, matched_tags, reason).
    """
    print(f"[castor] poll: agent={agent.registration.agent_name} categories={payload.categories} max_tasks={payload.max_tasks}")
    results = service.poll_tasks(agent, payload.categories, payload.max_tasks)
    print(f"[castor] poll result: {len(results)} tasks returned -> {[r['task_id'] for r in results]}")
    return {"total": len(results), "tasks": results}


# ── 2. Submit Proposal ───────────────────────────────────────────────

@router.post("/{task_id}/propose", response_class=JSONResponse)
def submit_proposal(task_id: str, payload: SubmitProposalRequest, agent=Depends(get_current_agent)):
    """Agent submits a structured execution plan to compete for a task.

    The proposal enters a "pending" state. The task publisher will review
    all proposals and choose one agent. Only after user confirmation will
    the task appear in the agent's execution queue.
    """
    proposal = service.submit_proposal(
        task_id, agent,
        plan_steps=payload.plan_steps,
        estimated_total_minutes=payload.estimated_total_minutes,
        message=payload.message,
    )
    if not proposal:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit proposal. Task may not be available or you already submitted one.",
        )
    return {"success": True, "proposal": proposal.model_dump(mode="json")}


@router.get("/my-proposals", response_class=JSONResponse)
def list_my_proposals(agent=Depends(get_current_agent)):
    """List all proposals submitted by this agent and their status."""
    store = get_store()
    proposals = [
        p.model_dump(mode="json")
        for p in store.proposals.values()
        if p.agent_id == agent.agent_id
    ]
    proposals.sort(key=lambda p: p["created_at"], reverse=True)
    return {"total": len(proposals), "proposals": proposals}


# ── 3. Get Next Task ─────────────────────────────────────────────────

@router.get("/next", response_class=JSONResponse)
def get_next_task(agent=Depends(get_current_agent)):
    """Get the next task to execute (FIFO queue, returns at most 1 task).

    Only returns tasks that have been confirmed by the user (status=assigned).
    The agent should complete or submit the current task before getting the next one.
    """
    tasks = service.list_assigned_tasks(agent)
    if not tasks:
        return {"has_task": False, "task": None, "queue_depth": 0}
    # FIFO: return the oldest assigned task (first in queue)
    next_task = tasks[0]
    # Find the accepted proposal for this task to include the execution plan
    store = get_store()
    accepted_proposal = None
    for p in store.proposals.values():
        if p.task_id == next_task.task_id and p.agent_id == agent.agent_id and p.status.value == "accepted":
            accepted_proposal = p
            break
    return {
        "has_task": True,
        "task": next_task.model_dump(mode="json"),
        "proposal": accepted_proposal.model_dump(mode="json") if accepted_proposal else None,
        "queue_depth": len(tasks),
        "message": f"Execute this task according to the approved proposal. {len(tasks) - 1} task(s) remain in the queue.",
    }


# ── 4. Execution progress ───────────────────────────────────────────

@router.post("/{task_id}/progress", response_class=JSONResponse)
def update_progress(task_id: str, payload: ProgressUpdateRequest, agent=Depends(get_current_agent)):
    """General progress update (percentage + message)."""
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")
    event = service.update_progress(task_id, payload.progress, payload.message)
    return {"success": True, "event": event}


@router.post("/{task_id}/step-progress", response_class=JSONResponse)
def update_step_progress(task_id: str, payload: StepProgressRequest, agent=Depends(get_current_agent)):
    """Update progress on a specific step of the execution plan."""
    event = service.update_step_progress(
        task_id, agent, payload.step_number, payload.status, payload.message,
    )
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")
    return {"success": True, "event": event}


# ── 5. File upload ───────────────────────────────────────────────────

@router.post("/{task_id}/upload", response_class=JSONResponse)
async def upload_file(task_id: str, file: UploadFile = File(...), agent=Depends(get_current_agent)):
    """Upload a result file for a task. Returns a permanent download URL.

    Supported: zip, tar.gz, pdf, csv, json, txt, images, etc.  Max 100 MB.
    """
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")

    meta = _save_uploaded_file(task_id, agent.agent_id, file)
    return {
        "success": True,
        "file": meta.model_dump(mode="json"),
    }


@router.get("/{task_id}/files", response_class=JSONResponse)
def list_task_files(task_id: str, agent=Depends(get_current_agent)):
    """List all files uploaded for a task."""
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")
    files = store.list_files_for_task(task_id)
    return {"total": len(files), "files": [f.model_dump(mode="json") for f in files]}


# ── 6. Submission ────────────────────────────────────────────────────

@router.post("/{task_id}/submit", response_class=JSONResponse)
async def submit_task(task_id: str, request: Request, agent=Depends(get_current_agent)):
    """Submit final task result.

    Supports both:
    - application/json
    - multipart/form-data with fields: output, proof, stats, files
    """
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.assigned_agent_id != agent.agent_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not assigned to this agent.")

    content_type = request.headers.get("content-type", "")
    uploaded_files: list[UploadedFileMeta] = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        try:
            output_raw = form.get("output", "{}")
            proof_raw = form.get("proof", "{}")
            stats_raw = form.get("stats", "{}")
            payload = SubmitTaskRequest(
                output=json.loads(str(output_raw)),
                proof=json.loads(str(proof_raw)),
                stats=json.loads(str(stats_raw)),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid multipart fields. 'output', 'proof', and 'stats' must be valid JSON strings.",
            ) from exc

        for item in form.getlist("files"):
            if isinstance(item, UploadFile) and item.filename:
                uploaded_files.append(_save_uploaded_file(task_id, agent.agent_id, item))
        # Also support single-file field name for convenience
        single_file = form.get("file")
        if isinstance(single_file, UploadFile) and single_file.filename:
            already_saved = any(f.original_filename == single_file.filename for f in uploaded_files)
            if not already_saved:
                uploaded_files.append(_save_uploaded_file(task_id, agent.agent_id, single_file))
    else:
        try:
            body = await request.json()
            payload = SubmitTaskRequest.model_validate(body)
        except Exception as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON request body.") from exc

    if not payload.output:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Output cannot be empty.")

    # Automatically attach uploaded file references to proof
    if uploaded_files:
        existing_ids = set(payload.proof.file_ids)
        existing_artifacts = set(payload.proof.artifacts)
        for f in uploaded_files:
            if f.file_id not in existing_ids:
                payload.proof.file_ids.append(f.file_id)
            if f.download_url not in existing_artifacts:
                payload.proof.artifacts.append(f.download_url)

    result = service.submit_task(
        task_id, agent, output=payload.output, proof=payload.proof, stats=payload.stats,
    )
    return {
        "success": True,
        "task": result.model_dump() if result else None,
        "files": [f.model_dump(mode="json") for f in uploaded_files],
        "settlement_state": "pending_verification",
    }
