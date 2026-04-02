"""Google OAuth2 (authorization code) helpers for user login."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from ....config import (
    BASE_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_STATE_SECRET,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

STATE_MAX_AGE_SECONDS = 600


def google_oauth_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def redirect_uri() -> str:
    if GOOGLE_OAUTH_REDIRECT_URI:
        return GOOGLE_OAUTH_REDIRECT_URI.rstrip("/")
    return f"{BASE_URL.rstrip('/')}/api/v1/users/auth/google/callback"


def build_authorization_url() -> str:
    if not google_oauth_enabled():
        raise RuntimeError("Google OAuth is not configured.")
    state = _sign_state({"ts": int(time.time()), "nonce": _random_nonce()})
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def verify_state(state: str | None) -> bool:
    if not state:
        return False
    return _verify_state(state)


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    if not google_oauth_enabled():
        raise RuntimeError("Google OAuth is not configured.")
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(GOOGLE_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()


def fetch_google_profile(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=30) as client:
        resp = client.get(GOOGLE_USERINFO_URL, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _random_nonce() -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(str(time.time_ns()).encode()).digest()).decode(
        "ascii"
    )[:16]


def _sign_state(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    secret = GOOGLE_OAUTH_STATE_SECRET.encode("utf-8")
    sig = hmac.new(secret, body, hashlib.sha256).digest()
    token = (
        base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
        + "."
        + base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    )
    return token


def _verify_state(token: str) -> bool:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        pad = "=" * (-len(body_b64) % 4)
        body = base64.urlsafe_b64decode(body_b64 + pad)
        sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        secret = GOOGLE_OAUTH_STATE_SECRET.encode("utf-8")
        expected = hmac.new(secret, body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return False
        payload = json.loads(body.decode("utf-8"))
        ts = int(payload.get("ts", 0))
        return (time.time() - ts) <= STATE_MAX_AGE_SECONDS
    except Exception:
        return False
