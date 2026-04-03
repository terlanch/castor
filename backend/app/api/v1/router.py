"""Collect all v1 sub-routers into a single APIRouter."""
from __future__ import annotations

from fastapi import APIRouter

from .agent.controller import router as agent_router
from .claim.controller import router as claim_router
from .task.controller import router as task_router
from .user.controller import router as user_router
from .admin.controller import router as admin_router
from .matching.controller import router as matching_router
from .files.controller import router as files_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(agent_router)
v1_router.include_router(claim_router)
v1_router.include_router(task_router)
v1_router.include_router(user_router)
v1_router.include_router(admin_router)
v1_router.include_router(matching_router)
v1_router.include_router(files_router)