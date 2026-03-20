"""Shared FastAPI dependencies – authentication & authorisation."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from ..config import ADMIN_TOKEN


def require_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> str:
    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Admin-Token header.",
        )
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
        )
    return x_admin_token


def get_current_agent(
    authorization: Optional[str] = Header(None),
):
    """Extract agent from Bearer token.  Raises 401 on failure."""
    from ..database import get_store

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )
    store = get_store()
    api_key = authorization.removeprefix("Bearer ").strip()
    agent = store.get_agent_by_api_key(api_key)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return agent


def get_current_user(
    authorization: Optional[str] = Header(None),
):
    """Extract user from Bearer token.  Raises 401 on failure."""
    from ..database import get_store

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )
    store = get_store()
    token = authorization.removeprefix("Bearer ").strip()
    user = store.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token.",
        )
    return user
