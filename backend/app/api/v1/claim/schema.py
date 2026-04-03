"""Claim flow – request / response schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ClaimContextResponse(BaseModel):
    agent_name: str
    description: str
    claimed: bool
    """UI step: 1 = email (or inbox wait), 2 = post tweet, 3 = paste tweet URL, 0 = done."""
    step: int = 1
    email_pending: bool = False
    """True when verification email was sent but link not yet clicked."""
    verification_code: str | None = None
    twitter_handle: str = "castor"


class ClaimRequestEmailRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=200)
    accept_tos: bool = False


class ClaimRequestEmailResponse(BaseModel):
    success: bool = True
    message: str = "Check your inbox for the verification link."
    verification_url: str | None = None
    """Populated in development when email is not sent; same URL that would appear in the email."""


class ClaimVerifyTweetRequest(BaseModel):
    tweet_url: str = Field(min_length=12, max_length=500)
