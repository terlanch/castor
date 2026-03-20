"""User business logic."""
from __future__ import annotations

from ....database import UserRecord, get_store
from .schema import UserLoginRequest, UserRegisterRequest, UserProfileResponse


def build_profile(user: UserRecord) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        balance=user.balance,
        frozen_balance=user.frozen_balance,
    )


def register(payload: UserRegisterRequest) -> UserRecord:
    return get_store().register_user(payload)


def login(payload: UserLoginRequest) -> UserRecord | None:
    return get_store().login_user(payload)


def topup(user: UserRecord, amount: int) -> UserRecord:
    return get_store().topup_user(user, amount)
