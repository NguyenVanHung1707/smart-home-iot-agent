"""FastAPI auth dependencies."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import src.services.devices as devices_mod
from src.services.auth import AuthError, AuthUser, authenticate_token

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing_token")
    try:
        record, _payload = authenticate_token(credentials.credentials, expected_typ="access")
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=exc.detail) from exc
    request.state.user = record
    return AuthUser(
        id=record["id"],
        email=record["email"],
        role=record["role"],
        display_name=record["display_name"],
    )


async def require_admin(request: Request, user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role != "ADMIN":
        logger.info("Forbidden admin route email=%s path=%s", user.email, request.url.path)
        raise HTTPException(status_code=403, detail="admin_required")
    return user


def get_current_registry(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
) -> Any:
    active_mode = mode or x_data_mode
    devices_mod.set_active_data_mode(active_mode)
    if not active_mode:
        return devices_mod.registry
    return devices_mod.get_registry(active_mode)
