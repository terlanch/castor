"""User domain – request / response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=200)
    display_name: str | None = Field(default=None, max_length=100)


class UserLoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=200)


class UserTopupRequest(BaseModel):
    amount: int = Field(ge=1, le=1_000_000)
    note: str = Field(default="Manual virtual top-up", min_length=2, max_length=200)


class UserAcceptTaskResultRequest(BaseModel):
    note: str = Field(default="Accepted by user.", min_length=2, max_length=500)


class UserRejectTaskResultRequest(BaseModel):
    note: str = Field(default="Rejected by user.", min_length=2, max_length=500)


class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    balance: int
    frozen_balance: int
    currency: str = "CASTOR_CREDIT"


class UserAuthResponse(BaseModel):
    user: UserProfileResponse
    access_token: str


class NaturalLanguageTaskRequest(BaseModel):
    """User submits a task in plain language."""
    description: str = Field(min_length=5, max_length=2000)
    max_budget: int = Field(ge=1, le=1_000_000)
