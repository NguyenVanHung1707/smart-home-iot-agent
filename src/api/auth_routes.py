"""Authentication and user-management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import AuthUser, current_user, require_admin
from src.config import get_settings
from src.models.schemas import (
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UpdateUserRequest,
    UserPublic,
)
from src.services.auth import AuthError, authenticate_token, login_rate_limited, token_response
from src.services.users import users

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    settings = get_settings()
    email = request.email.strip().lower()
    if login_rate_limited(email):
        logger.info("Login rate limited email=%s", email)
        raise HTTPException(status_code=429, detail="too_many_login_attempts")
    user, error = users.verify_login(email, request.password)
    if error:
        if error == "invalid_credentials":
            users.record_failed_login(email, settings.login_lockout_threshold)
        logger.info("Login failed email=%s reason=%s", email, error)
        raise HTTPException(status_code=401, detail=error)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    users.record_success(user["id"])
    fresh_user = users.get(user["id"])
    if fresh_user is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    logger.info("Login succeeded email=%s role=%s", email, fresh_user["role"])
    return token_response(fresh_user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest) -> TokenResponse:
    try:
        user, _payload = authenticate_token(request.refresh_token, expected_typ="refresh")
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=exc.detail) from exc
    return token_response(user)


@router.post("/logout")
async def logout(user: AuthUser = Depends(current_user)) -> dict[str, str]:
    users.bump_token_version(user.id)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserPublic)
async def me(user: AuthUser = Depends(current_user)) -> UserPublic:
    record = users.get(user.id)
    if record is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    return users.public_from_record(record)


@router.get("/users", response_model=list[UserPublic], dependencies=[Depends(require_admin)])
async def list_users() -> list[UserPublic]:
    return users.list()


def _create_user(request: CreateUserRequest) -> UserPublic:
    try:
        return users.create(request.email, request.password, request.display_name, request.role)
    except ValueError as exc:
        if str(exc) == "email_exists":
            raise HTTPException(status_code=409, detail="email_exists") from exc
        raise


@router.post("/register", response_model=UserPublic, status_code=201, dependencies=[Depends(require_admin)])
async def register_user(request: CreateUserRequest) -> UserPublic:
    return _create_user(request)


@router.post("/users", response_model=UserPublic, status_code=201, dependencies=[Depends(require_admin)])
async def create_user(request: CreateUserRequest) -> UserPublic:
    return _create_user(request)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    admin: AuthUser = Depends(require_admin),
) -> UserPublic:
    if user_id == admin.id and (request.locked is True or request.role == "MEMBER"):
        raise HTTPException(status_code=409, detail="cannot_disable_self")
    updated = users.update(
        user_id,
        {
            "display_name": request.display_name,
            "role": request.role,
            "locked": request.locked,
            "password": request.password,
        },
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return updated
