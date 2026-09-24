"""JSON-backed user store for local Homing Hub auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import string
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from src.config import Settings, get_settings
from src.models.schemas import Role, UserPublic

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored_hash.split("$", 5)
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except Exception:
        return False
    return hmac.compare_digest(candidate, expected)


class UserStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or get_settings().users_file)
        self._users: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.load()

    def configure(self, storage_path: str | Path) -> None:
        with self._lock:
            self.storage_path = Path(storage_path)
            self._users = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                from src.database import db_load_users, is_postgres_enabled

                if is_postgres_enabled():
                    db_users = db_load_users()
                    if db_users:
                        self._users = db_users
                        return
            except Exception:
                pass

            if not self.storage_path.exists():
                self._users = {}
                return
            try:
                raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    self._users = {}
                    return
                self._users = {item["id"]: item for item in raw if isinstance(item, dict) and item.get("id")}
            except Exception:
                self._users = {}

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
            payload = list(self._users.values())
            tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_path, self.storage_path)
        except Exception:
            pass

        try:
            from src.database import db_save_users, is_postgres_enabled

            if is_postgres_enabled():
                db_save_users(self._users)
        except Exception:
            pass

    def bootstrap_admin(self, settings: Settings | None = None) -> str | None:
        settings = settings or get_settings()
        with self._lock:
            admin_email = normalize_email(settings.bootstrap_admin_email or "admin@homing.dev")
            has_admin = any(normalize_email(item.get("email", "")) == admin_email for item in self._users.values())
            admin_pw_to_return = None
            if not has_admin:
                password = settings.bootstrap_admin_password or generate_password(16)
                user_id = str(uuid4())
                self._users[user_id] = {
                    "id": user_id,
                    "email": admin_email,
                    "display_name": "Home Admin",
                    "role": "ADMIN",
                    "password_hash": hash_password(password),
                    "token_version": 0,
                    "locked": False,
                    "failed_attempts": 0,
                    "created_at": _now(),
                    "last_login_at": None,
                }
                if not settings.bootstrap_admin_password:
                    admin_pw_to_return = password
                self._save_locked()

            return admin_pw_to_return

    def create(self, email: str, password: str, display_name: str, role: Role = "MEMBER") -> UserPublic:
        email = normalize_email(email)
        with self._lock:
            if any(item.get("email") == email for item in self._users.values()):
                raise ValueError("email_exists")
            user_id = str(uuid4())
            record = {
                "id": user_id,
                "email": email,
                "display_name": display_name.strip(),
                "role": role,
                "password_hash": hash_password(password),
                "token_version": 0,
                "locked": False,
                "failed_attempts": 0,
                "created_at": _now(),
                "last_login_at": None,
            }
            self._users[user_id] = record
            self._save_locked()
            return self.public_from_record(record)

    def update(self, user_id: str, updates: dict[str, Any]) -> UserPublic | None:
        with self._lock:
            record = self._users.get(user_id)
            if record is None:
                return None
            security_changed = False
            if updates.get("display_name") is not None:
                record["display_name"] = str(updates["display_name"]).strip()
            if updates.get("role") is not None and updates["role"] != record["role"]:
                record["role"] = updates["role"]
                security_changed = True
            if updates.get("locked") is not None and updates["locked"] != record["locked"]:
                record["locked"] = bool(updates["locked"])
                security_changed = True
            if updates.get("password") is not None:
                record["password_hash"] = hash_password(str(updates["password"]))
                security_changed = True
            if security_changed:
                record["token_version"] = int(record.get("token_version", 0)) + 1
            self._save_locked()
            return self.public_from_record(record)

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._users.get(user_id)
            return deepcopy(record) if record else None

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        email = normalize_email(email)
        with self._lock:
            for record in self._users.values():
                if record.get("email") == email:
                    return deepcopy(record)
        return None

    def list(self) -> list[UserPublic]:
        with self._lock:
            return [self.public_from_record(item) for item in self._users.values()]

    def verify_login(self, email: str, password: str) -> tuple[dict[str, Any] | None, str | None]:
        record = self.get_by_email(email)
        if record is None:
            return None, "invalid_credentials"
        if record.get("locked"):
            return None, "account_locked"
        if not verify_password(password, record.get("password_hash", "")):
            return None, "invalid_credentials"
        return record, None

    def record_failed_login(self, email: str, lockout_threshold: int) -> None:
        email = normalize_email(email)
        with self._lock:
            for record in self._users.values():
                if record.get("email") == email:
                    record["failed_attempts"] = int(record.get("failed_attempts", 0)) + 1
                    if record["failed_attempts"] >= lockout_threshold:
                        record["locked"] = True
                        record["token_version"] = int(record.get("token_version", 0)) + 1
                    self._save_locked()
                    return

    def record_success(self, user_id: str) -> None:
        with self._lock:
            record = self._users.get(user_id)
            if record is None:
                return
            record["failed_attempts"] = 0
            record["last_login_at"] = _now()
            self._save_locked()

    def bump_token_version(self, user_id: str) -> None:
        with self._lock:
            record = self._users.get(user_id)
            if record is None:
                return
            record["token_version"] = int(record.get("token_version", 0)) + 1
            self._save_locked()

    @staticmethod
    def public_from_record(record: dict[str, Any]) -> UserPublic:
        return UserPublic(
            id=record["id"],
            email=record["email"],
            display_name=record["display_name"],
            role=record["role"],
            locked=bool(record.get("locked", False)),
            created_at=record["created_at"],
        )


users = UserStore()
