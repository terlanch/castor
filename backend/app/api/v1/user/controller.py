"""User HTTP endpoints."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse

from ....common.deps import get_current_user
from ....config import BASE_URL, FRONTEND_BASE_URL, GOOGLE_CLIENT_ID
from ....database import get_store
from ..matching.service import build_candidates_for_task
from ..task import service as task_service
from ..task.schema import CreateTaskRequest, TaskStatus
from .schema import (
    NaturalLanguageTaskRequest,
    UserAcceptTaskResultRequest,
    UserAuthResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRejectTaskResultRequest,
    UserRegisterRequest,
    UserTopupRequest,
)
from . import service
from .oauth_google import (
    build_authorization_url,
    exchange_code_for_tokens,
    fetch_google_profile,
    google_oauth_enabled,
    redirect_uri as google_redirect_uri,
    verify_state,
)

router = APIRouter(prefix="/users", tags=["User"])


@router.get("/auth/google/status", response_class=JSONResponse)
def google_auth_status() -> dict:
    """Whether Google OAuth is configured, and the exact redirect_uri sent to Google (for Console setup)."""
    enabled = google_oauth_enabled()
    out: dict = {"enabled": enabled}
    if not enabled:
        return out
    out["castor_base_url"] = BASE_URL.rstrip("/")
    out["redirect_uri"] = google_redirect_uri()
    out["google_client_id"] = GOOGLE_CLIENT_ID
    out["hint"] = (
        "In Google Cloud Console → APIs & Credentials → your OAuth 2.0 Client ID (type: Web application) → "
        "Authorized redirect URIs → add the value of redirect_uri EXACTLY (scheme, host, port, path). "
        "If CASTOR_BASE_URL is set in your shell, it overrides .env and changes redirect_uri."
    )
    return out


@router.get("/auth/google")
def google_login_start():
    """Redirect browser to Google consent screen (authorization code flow)."""
    if not google_oauth_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured. Set CASTOR_GOOGLE_CLIENT_ID and CASTOR_GOOGLE_CLIENT_SECRET.",
        )
    return RedirectResponse(url=build_authorization_url(), status_code=302)


@router.get("/auth/google/callback")
def google_login_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth redirect target: exchange code, upsert user, redirect to SPA with token in URL fragment."""
    fe = FRONTEND_BASE_URL.rstrip("/")
    if error or not code:
        return RedirectResponse(
            url=f"{fe}/oauth/callback#error={quote(error or 'access_denied')}",
            status_code=302,
        )
    if not verify_state(state):
        return RedirectResponse(url=f"{fe}/oauth/callback#error=invalid_state", status_code=302)
    try:
        tokens = exchange_code_for_tokens(code)
        access = tokens.get("access_token")
        if not access:
            raise ValueError("missing access_token")
        profile = fetch_google_profile(access)
        sub = profile.get("sub")
        if not sub:
            raise ValueError("missing sub")
        user = get_store().upsert_google_user(
            google_sub=sub,
            email=profile.get("email"),
            display_name=profile.get("name"),
        )
    except Exception:
        return RedirectResponse(url=f"{fe}/oauth/callback#error=oauth_failed", status_code=302)
    tok = quote(user.access_token, safe="")
    return RedirectResponse(url=f"{fe}/oauth/callback#access_token={tok}", status_code=302)


@router.post("/register", response_model=UserAuthResponse)
def register_user(payload: UserRegisterRequest) -> UserAuthResponse:
    user = service.register(payload)
    return UserAuthResponse(user=service.build_profile(user), access_token=user.access_token)


@router.post("/login", response_model=UserAuthResponse)
def login_user(payload: UserLoginRequest) -> UserAuthResponse:
    user = service.login(payload)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    return UserAuthResponse(user=service.build_profile(user), access_token=user.access_token)


@router.get("/me", response_model=UserProfileResponse)
def current_user_profile(user=Depends(get_current_user)) -> UserProfileResponse:
    return service.build_profile(user)


@router.post("/topup", response_model=UserProfileResponse)
def topup_user(payload: UserTopupRequest, user=Depends(get_current_user)) -> UserProfileResponse:
    user = service.topup(user, payload.amount)
    return service.build_profile(user)


@router.get("/tasks", response_class=JSONResponse)
def list_user_tasks(user=Depends(get_current_user)):
    store = get_store()
    tasks = [t.model_dump(mode="json") for t in store.list_user_tasks(user.user_id)]
    return {"total": len(tasks), "tasks": tasks}


@router.post("/tasks", response_class=JSONResponse)
def create_user_task(payload: CreateTaskRequest, user=Depends(get_current_user)):
    try:
        task = task_service.create_task_for_user(user, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"success": True, "task": task.model_dump(mode="json")}


@router.post("/tasks/natural", response_class=JSONResponse)
def create_nl_task(payload: NaturalLanguageTaskRequest, user=Depends(get_current_user)):
    """Accept a free-form task description, structure it via LLM, then create."""
    try:
        task, structured = task_service.create_nl_task_for_user(user, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "success": True,
        "task": task.model_dump(mode="json"),
        "structured_from": {
            "tags": structured.get("tags", []),
            "skills_required": structured.get("skills_required", []),
            "region": structured.get("region", "global"),
            "category": structured.get("category", "general"),
        },
    }


@router.get("/tasks/{task_id}/proposals", response_class=JSONResponse)
def list_task_proposals(task_id: str, user=Depends(get_current_user)):
    """View all proposals submitted by agents for a specific task."""
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.owner_user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    proposals = store.list_proposals_for_task(task_id)
    return {
        "task_id": task_id,
        "task_title": task.title,
        "task_status": task.status.value,
        "total": len(proposals),
        "proposals": [p.model_dump(mode="json") for p in proposals],
    }


@router.post("/tasks/{task_id}/proposals/{proposal_id}/accept", response_class=JSONResponse)
def accept_proposal(task_id: str, proposal_id: str, user=Depends(get_current_user)):
    """User accepts a specific agent's proposal → task assigned to that agent."""
    store = get_store()
    proposal = store.accept_proposal(proposal_id, user)
    if not proposal:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Cannot accept proposal. It may not exist, or task is no longer available.",
        )
    task = store.get_task(task_id)
    return {
        "success": True,
        "proposal": proposal.model_dump(mode="json"),
        "task": task.model_dump(mode="json") if task else None,
    }


@router.post("/tasks/{task_id}/proposals/{proposal_id}/reject", response_class=JSONResponse)
def reject_proposal(task_id: str, proposal_id: str, user=Depends(get_current_user)):
    """User rejects a specific agent's proposal."""
    store = get_store()
    proposal = store.reject_proposal(proposal_id, user)
    if not proposal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Proposal not found.")
    return {"success": True, "proposal": proposal.model_dump(mode="json")}


@router.get("/tasks/{task_id}/progress", response_class=JSONResponse)
def get_task_progress(task_id: str, user=Depends(get_current_user)):
    """View step-level execution progress for a task."""
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.owner_user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    # Find accepted proposal for step details
    accepted_proposal = None
    for p in store.proposals.values():
        if p.task_id == task_id and p.status.value == "accepted":
            accepted_proposal = p
            break
    progress_logs = store.progress_logs.get(task_id, [])
    # Include submission result if the Agent has submitted
    submission_data = None
    if task.submission:
        submission_data = task.submission.model_dump(mode="json")
    # Include uploaded files
    uploaded_files = store.list_files_for_task(task_id)
    return {
        "task_id": task_id,
        "task_title": task.title,
        "status": task.status.value,
        "progress": task.progress,
        "assigned_agent_id": task.assigned_agent_id,
        "proposal": accepted_proposal.model_dump(mode="json") if accepted_proposal else None,
        "progress_logs": progress_logs,
        "submission": submission_data,
        "files": [f.model_dump(mode="json") for f in uploaded_files],
    }


@router.post("/tasks/{task_id}/accept-result", response_class=JSONResponse)
def accept_task_result(task_id: str, payload: UserAcceptTaskResultRequest, user=Depends(get_current_user)):
    store = get_store()
    existing_task = store.get_task(task_id)
    if not existing_task or existing_task.owner_user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if existing_task.status not in {TaskStatus.submitted, TaskStatus.verified}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Task result can only be accepted after submission. Current status: {existing_task.status.value}.",
        )
    task = store.accept_task_result(user, task_id, payload.note)
    if not task:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unable to accept task result.")
    return {"success": True, "task": task.model_dump(mode="json")}


@router.post("/tasks/{task_id}/reject-result", response_class=JSONResponse)
def reject_task_result(task_id: str, payload: UserRejectTaskResultRequest, user=Depends(get_current_user)):
    store = get_store()
    task = store.get_task(task_id)
    if not task or task.owner_user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.status not in {TaskStatus.submitted, TaskStatus.verified}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Only submitted results can be rejected. Current status: {task.status.value}.",
        )
    updated = store.reject_submission(task_id, payload.note)
    if not updated:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unable to reject task result.")
    build_candidates_for_task(store, updated)
    return {"success": True, "task": updated.model_dump(mode="json")}
