"""Accounts: register, sign in, who am I."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.deps import current_user, token_secret
from src.api.schemas.auth_schemas import (
    DemoAccountResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.core.auth.demo_accounts import demo_accounts
from src.core.auth.security import (
    LoginThrottle,
    create_access_token,
    hash_password,
    verify_password,
)
from src.core.auth.users import SqlUserRepository, User, UsernameTakenError
from src.core.config import get_settings
from src.core.storage.db import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_throttle = LoginThrottle()
# Checked when the account does not exist, so that "unknown user" takes as long as "wrong password".
_DUMMY_HASH = hash_password("no-such-user")


def _token_response(user: User) -> TokenResponse:
    token, lifetime = create_access_token(user.id, user.role, token_secret(), get_settings().jwt_expire_hours)
    return TokenResponse(
        access_token=token, expires_in=lifetime,
        user=UserResponse(id=user.id, username=user.username, full_name=user.full_name, role=user.role),  # type: ignore[arg-type]
    )


@router.post("/register", status_code=201, response_model=TokenResponse)
def register(req: RegisterRequest) -> TokenResponse:
    """Open registration. New accounts are always ordinary users; the admin is created from the environment."""
    try:
        user = SqlUserRepository(get_db_engine()).create_user(
            req.username, hash_password(req.password), req.full_name, role="user"
        )
    except UsernameTakenError as exc:
        raise HTTPException(409, "This username is already taken.") from exc
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request) -> TokenResponse | JSONResponse:
    key = f"{req.username.strip().lower()}|{request.client.host if request.client else '-'}"
    if _throttle.is_blocked(key):
        wait = _throttle.retry_after(key)
        return JSONResponse(
            {"error": f"Too many failed attempts. Try again in {wait} seconds."},
            status_code=429, headers={"Retry-After": str(wait)},
        )
    found = SqlUserRepository(get_db_engine()).get_with_hash(req.username)
    valid = verify_password(req.password, found[1] if found else _DUMMY_HASH)
    if not found or not valid:
        _throttle.record_failure(key)
        raise HTTPException(401, "Wrong username or password.")
    _throttle.reset(key)
    return _token_response(found[0])


@router.get("/demo-accounts", response_model=list[DemoAccountResponse])
def get_demo_accounts() -> list[DemoAccountResponse]:
    """Ready-made accounts for the one-click boxes. Empty unless DEV_QUICK_LOGIN=true (development only)."""
    if not get_settings().dev_quick_login:
        return []
    return [DemoAccountResponse(**a.__dict__) for a in demo_accounts()]


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, full_name=user.full_name, role=user.role)  # type: ignore[arg-type]
