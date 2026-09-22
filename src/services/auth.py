"""JWT helpers and login throttling for local auth."""

from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

import jwt

from src.config import get_settings
from src.models.schemas import TokenResponse
from src.services.users import UserStore, users

logger = logging.getLogger(__name__)
_dev_jwt_secret = secrets.token_urlsafe(48)
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = Lock()


class AuthError(Exception):
    def __init__(self, detail: str = "invalid_token") -> None:
        self.detail = detail


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    role: str
    display_name: str


def _jwt_secret() -> str:
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.app_env == "production":
        logger.warning("JWT_SECRET is empty in production; generated tokens will be invalid after restart")
    return _dev_jwt_secret


def _claims(user: dict[str, Any], token_type: str, expires_delta: timedelta) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "sub": user["id"],
        "role": user["role"],
        "tv": int(user.get("token_version", 0)),
        "typ": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid4()),
    }


def create_access_token(user: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(
        _claims(user, "access", timedelta(minutes=settings.access_token_ttl_minutes)),
        _jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(
        _claims(user, "refresh", timedelta(days=settings.refresh_token_ttl_days)),
        _jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def token_response(user: dict[str, Any]) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserStore.public_from_record(user),
    )


def decode_token(token: str, expected_typ: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid_token") from exc
    if payload.get("typ") != expected_typ:
        raise AuthError("invalid_token_type")
    return payload


def authenticate_token(token: str, expected_typ: str = "access") -> tuple[dict[str, Any], dict[str, Any]]:
    payload = decode_token(token, expected_typ)
    user_id = str(payload.get("sub") or "")
    record = users.get(user_id)
    if record is None:
        raise AuthError("invalid_token")
    if record.get("locked"):
        raise AuthError("account_locked")
    if int(payload.get("tv", -1)) != int(record.get("token_version", 0)):
        raise AuthError("invalid_token")
    return record, payload


def login_rate_limited(email: str) -> bool:
    settings = get_settings()
    now = time.monotonic()
    key = email.strip().lower()
    with _attempts_lock:
        bucket = _attempts[key]
        while bucket and now - bucket[0] > settings.login_rate_limit_window_seconds:
            bucket.popleft()
        if len(bucket) >= settings.login_rate_limit_attempts:
            return True
        bucket.append(now)
        return False


def clear_login_rate_limits() -> None:
    with _attempts_lock:
        _attempts.clear()
