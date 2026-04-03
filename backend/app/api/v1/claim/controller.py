"""Public HTTP endpoints for agent owner claim flow."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from ....database import get_store
from ..user.schema import UserAuthResponse
from .schema import (
    ClaimContextResponse,
    ClaimRequestEmailRequest,
    ClaimRequestEmailResponse,
    ClaimVerifyTweetRequest,
)
from . import service

router = APIRouter(prefix="/claim", tags=["Claim"])


@router.get("/verify-email")
def verify_claim_email(token: str) -> RedirectResponse:
    url, _session = service.verify_email_token(token)
    return RedirectResponse(url=url, status_code=302)


@router.get("/{claim_token}/context", response_model=ClaimContextResponse)
def get_claim_context(claim_token: str) -> ClaimContextResponse:
    store = get_store()
    agent = store.get_agent_by_claim_token(claim_token)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invalid or unknown claim link.")
    data = service.build_claim_context(agent)
    return ClaimContextResponse(**data)


@router.post("/{claim_token}/request-email", response_model=ClaimRequestEmailResponse)
def request_claim_email(claim_token: str, payload: ClaimRequestEmailRequest) -> ClaimRequestEmailResponse:
    store = get_store()
    agent = store.get_agent_by_claim_token(claim_token)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invalid or unknown claim link.")
    try:
        verify_url, msg = service.request_email(
            agent,
            email=str(payload.email),
            username=payload.username,
            password=payload.password,
            accept_tos=payload.accept_tos,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ClaimRequestEmailResponse(
        success=True,
        message=msg,
        verification_url=verify_url,
    )


@router.post("/{claim_token}/verify-tweet", response_model=UserAuthResponse)
def verify_claim_tweet(claim_token: str, payload: ClaimVerifyTweetRequest) -> UserAuthResponse:
    store = get_store()
    agent = store.get_agent_by_claim_token(claim_token)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invalid or unknown claim link.")
    profile, access_token = service.verify_tweet_and_complete(agent, payload.tweet_url)
    return UserAuthResponse(user=profile, access_token=access_token)
