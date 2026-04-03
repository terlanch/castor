"""Claim flow: email handoff (dev returns link), Twitter oEmbed tweet check.

oEmbed is unauthenticated and may be rate-limited or change; see plan notes.
"""
from __future__ import annotations

import html as html_module
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from ....config import (
    BASE_URL,
    CASTOR_TWITTER_HANDLE,
    CLAIM_EMAIL_VERIFY_TTL_MINUTES,
    FRONTEND_BASE_URL,
)
from ....database import AgentClaimSession, AgentRecord, get_store
from ..user.service import build_profile


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_twitter_oembed_html(tweet_url: str) -> str:
    """GET Twitter publish oEmbed; returns HTML snippet or raises."""
    api = "https://publish.twitter.com/oembed"
    qs = urllib.parse.urlencode({"url": tweet_url.strip()})
    req = urllib.request.Request(
        f"{api}?{qs}",
        headers={"User-Agent": "CastorClaim/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Twitter oEmbed HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Could not reach Twitter oEmbed: {e.reason}") from e
    data = json.loads(raw)
    return (data.get("html") or "").strip()


def tweet_url_looks_valid(url: str) -> bool:
    u = url.strip().lower()
    if "twitter.com/" in u or "x.com/" in u:
        return bool(re.search(r"/status(?:es)?/\d+", u))
    return False


def oembed_html_contains_verification(
    html: str, *, verification_code: str, agent_name: str, twitter_handle: str,
) -> bool:
    """Match verification token and agent name in oEmbed HTML (blockquote text)."""
    plain = html_module.unescape(re.sub(r"<[^>]+>", " ", html))
    plain_lower = plain.lower()
    code_lower = verification_code.lower()
    if code_lower not in plain_lower:
        return False
    if agent_name.lower() not in plain_lower:
        return False
    handle = twitter_handle.lstrip("@").lower()
    if handle and f"@{handle}" not in plain_lower:
        return False
    return True


def build_claim_context(agent: AgentRecord) -> dict:
    store = get_store()
    handle = CASTOR_TWITTER_HANDLE.lstrip("@")
    if agent.owner_user_id:
        return {
            "agent_name": agent.registration.agent_name,
            "description": agent.registration.description,
            "claimed": True,
            "step": 0,
            "verification_code": None,
            "twitter_handle": handle,
        }
    step = 1
    email_pending = False
    for s in store.claim_sessions.values():
        if s.agent_id != agent.agent_id or s.claim_token != agent.claim_token:
            continue
        if s.status == "email_verified":
            step = 2
            break
        if s.status == "pending_email":
            email_pending = True
            break
    return {
        "agent_name": agent.registration.agent_name,
        "description": agent.registration.description,
        "claimed": False,
        "step": step,
        "email_pending": email_pending,
        "verification_code": agent.verification_code,
        "twitter_handle": handle,
    }


def request_email(
    agent: AgentRecord,
    *,
    email: str,
    username: str,
    password: str,
    accept_tos: bool,
) -> tuple[str | None, str]:
    """Returns (verification_url for dev, user-facing message)."""
    if not accept_tos:
        raise ValueError("You must accept the terms to continue.")
    if agent.owner_user_id:
        raise ValueError("This agent is already claimed.")
    store = get_store()
    if store.find_user_by_username(username):
        raise ValueError("That username is already taken. Pick another or log in first.")
    store.expire_open_claim_sessions_for_agent(agent.agent_id)
    now = _utc_now()
    expires = now + timedelta(minutes=CLAIM_EMAIL_VERIFY_TTL_MINUTES)
    from secrets import token_urlsafe
    from uuid import uuid4

    from ....database import hash_password

    session = AgentClaimSession(
        session_id=str(uuid4()),
        agent_id=agent.agent_id,
        claim_token=agent.claim_token,
        email=email.strip().lower(),
        username=username.strip(),
        password_hash=hash_password(password),
        email_verify_token=token_urlsafe(32),
        email_verify_expires_at=expires.isoformat(),
        status="pending_email",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    store.save_claim_session(session)
    verify_link = (
        f"{BASE_URL.rstrip('/')}/api/v1/claim/verify-email"
        f"?token={urllib.parse.quote(session.email_verify_token, safe='')}"
    )
    return verify_link, "Verification link created. In production this would be emailed to you."


def verify_email_token(verify_token: str) -> tuple[str, AgentClaimSession | None]:
    """Returns (redirect_url, session if success)."""
    store = get_store()
    session = store.get_claim_session_by_verify_token(verify_token)
    if not session:
        return f"{FRONTEND_BASE_URL.rstrip('/')}/login?error=claim_email_invalid", None
    if session.status != "pending_email":
        return (
            f"{FRONTEND_BASE_URL.rstrip('/')}/claim/{session.claim_token}?error=already_used",
            None,
        )
    exp = datetime.fromisoformat(session.email_verify_expires_at)
    if _utc_now() > exp:
        session.status = "expired"
        session.updated_at = _utc_now().isoformat()
        store.save_claim_session(session)
        return (
            f"{FRONTEND_BASE_URL.rstrip('/')}/claim/{session.claim_token}?error=expired",
            None,
        )
    session.status = "email_verified"
    session.email_verified_at = _utc_now().isoformat()
    session.updated_at = session.email_verified_at
    store.save_claim_session(session)
    ok = f"{FRONTEND_BASE_URL.rstrip('/')}/claim/{session.claim_token}?step=2"
    return ok, session


def verify_tweet_and_complete(agent: AgentRecord, tweet_url: str):
    """Create user, attach owner, return UserAuthResponse parts."""
    from fastapi import HTTPException, status

    if agent.owner_user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Agent already claimed.")
    if not tweet_url_looks_valid(tweet_url):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Paste a full tweet URL from x.com or twitter.com (must include /status/...).",
        )
    store = get_store()
    session: AgentClaimSession | None = None
    candidates: list[AgentClaimSession] = []
    for s in store.claim_sessions.values():
        if (
            s.agent_id == agent.agent_id
            and s.claim_token == agent.claim_token
            and s.status == "email_verified"
        ):
            candidates.append(s)
    if not candidates:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Verify your email first, or start over from step 1.",
        )
    session = max(candidates, key=lambda x: x.updated_at or x.created_at)
    try:
        embed_html = fetch_twitter_oembed_html(tweet_url)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not load tweet preview ({e}). Try again or confirm the tweet is public.",
        ) from e
    handle = CASTOR_TWITTER_HANDLE.lstrip("@")
    if not oembed_html_contains_verification(
        embed_html,
        verification_code=agent.verification_code,
        agent_name=agent.registration.agent_name,
        twitter_handle=handle,
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Tweet text must include your verification code, agent name, and the Castor handle.",
        )
    if store.find_user_by_username(session.username):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Username was taken after you started. Start over with a new username.",
        )
    try:
        user = store.create_user_from_claim(
            username=session.username,
            password_hash=session.password_hash,
            display_name=session.username,
        )
    except ValueError as e:
        if str(e) == "username_taken":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Username already taken.",
            ) from e
        raise
    store.set_agent_owner(agent, user.user_id)
    session.status = "completed"
    session.tweet_url = tweet_url.strip()
    session.tweet_verified_at = datetime.now(timezone.utc).isoformat()
    session.updated_at = session.tweet_verified_at
    store.save_claim_session(session)
    profile = build_profile(user)
    return profile, user.access_token
