"""PostgreSQL database engine, SQLAlchemy ORM models, and automatic migration."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    role = Column(String(32), default="MEMBER", nullable=False)
    password_hash = Column(Text, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    locked = Column(Boolean, default=False, nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(String(64), nullable=False)
    last_login_at = Column(String(64), nullable=True)


class DeviceDB(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, index=True)
    mode = Column(String(32), primary_key=True, default="simulator", index=True)
    name = Column(String(255), nullable=False)
    room = Column(String(255), nullable=False)
    kind = Column(String(64), nullable=False)
    online = Column(Boolean, default=True, nullable=False)
    state = Column(JSON, default=dict, nullable=False)
    capabilities = Column(JSON, default=dict, nullable=False)
    updated_at = Column(String(64), nullable=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        db_url = settings.database_url
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            _engine = create_engine(db_url, connect_args=connect_args)
        else:
            _engine = create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_postgres_enabled() -> bool:
    settings = get_settings()
    return settings.database_url.startswith("postgresql")


def init_db() -> bool:
    """Initialize database tables and seed initial data if empty."""
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")

        # Seed Users from data/users.json if table is empty
        with get_db_session() as session:
            user_count = session.query(UserDB).count()
            if user_count == 0:
                users_file = Path(get_settings().users_file)
                if not users_file.exists() and Path("data/users.json").exists():
                    users_file = Path("data/users.json")
                if users_file.exists():
                    try:
                        raw = json.loads(users_file.read_text(encoding="utf-8"))
                        if isinstance(raw, list):
                            for item in raw:
                                user = UserDB(
                                    id=item["id"],
                                    email=item["email"],
                                    display_name=item.get("display_name", "User"),
                                    role=item.get("role", "MEMBER"),
                                    password_hash=item["password_hash"],
                                    token_version=item.get("token_version", 0),
                                    locked=item.get("locked", False),
                                    failed_attempts=item.get("failed_attempts", 0),
                                    created_at=item.get("created_at", datetime.now(UTC).isoformat()),
                                    last_login_at=item.get("last_login_at"),
                                )
                                session.add(user)
                            logger.info("Seeded %d users from %s into PostgreSQL", len(raw), users_file)
                    except Exception as e:
                        logger.error("Failed to seed users into database: %s", e)

            # Seed Devices for simulator mode
            sim_count = session.query(DeviceDB).filter_by(mode="simulator").count()
            if sim_count == 0:
                dev_file = Path(get_settings().device_storage_path)
                if not dev_file.exists() and Path("data/devices.json").exists():
                    dev_file = Path("data/devices.json")
                if dev_file.exists():
                    try:
                        raw = json.loads(dev_file.read_text(encoding="utf-8"))
                        if isinstance(raw, list):
                            for item in raw:
                                dev = DeviceDB(
                                    id=item["id"],
                                    mode="simulator",
                                    name=item["name"],
                                    room=item.get("room", "Chưa phân loại"),
                                    kind=item.get("kind", "light"),
                                    online=item.get("online", True),
                                    state=item.get("state", {}),
                                    capabilities=item.get("capabilities", {}),
                                    updated_at=datetime.now(UTC).isoformat(),
                                )
                                session.add(dev)
                            logger.info("Seeded %d simulator devices from %s into PostgreSQL", len(raw), dev_file)
                    except Exception as e:
                        logger.error("Failed to seed simulator devices: %s", e)

            # Seed Devices for real mode
            real_count = session.query(DeviceDB).filter_by(mode="real").count()
            if real_count == 0:
                real_file = Path(get_settings().real_device_storage_path)
                if not real_file.exists() and Path("data/devices_real.json").exists():
                    real_file = Path("data/devices_real.json")
                if real_file.exists():
                    try:
                        raw = json.loads(real_file.read_text(encoding="utf-8"))
                        if isinstance(raw, list):
                            for item in raw:
                                dev = DeviceDB(
                                    id=item["id"],
                                    mode="real",
                                    name=item["name"],
                                    room=item.get("room", "Chưa phân loại"),
                                    kind=item.get("kind", "light"),
                                    online=item.get("online", True),
                                    state=item.get("state", {}),
                                    capabilities=item.get("capabilities", {}),
                                    updated_at=datetime.now(UTC).isoformat(),
                                )
                                session.add(dev)
                            logger.info("Seeded %d real devices from %s into PostgreSQL", len(raw), real_file)
                    except Exception as e:
                        logger.error("Failed to seed real devices: %s", e)

        return True
    except Exception as e:
        logger.error("Could not initialize database: %s", e)
        return False


def db_load_users() -> dict[str, dict[str, Any]]:
    """Fetch all users from database as a dictionary."""
    with get_db_session() as session:
        users = session.query(UserDB).all()
        return {
            u.id: {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "password_hash": u.password_hash,
                "token_version": u.token_version,
                "locked": u.locked,
                "failed_attempts": u.failed_attempts,
                "created_at": u.created_at,
                "last_login_at": u.last_login_at,
            }
            for u in users
        }


def db_save_users(users: dict[str, dict[str, Any]]) -> None:
    """Upsert all user records into database."""
    with get_db_session() as session:
        for uid, record in users.items():
            user_obj = session.query(UserDB).filter_by(id=uid).first()
            if user_obj:
                user_obj.email = record["email"]
                user_obj.display_name = record["display_name"]
                user_obj.role = record["role"]
                user_obj.password_hash = record["password_hash"]
                user_obj.token_version = record.get("token_version", 0)
                user_obj.locked = record.get("locked", False)
                user_obj.failed_attempts = record.get("failed_attempts", 0)
                user_obj.last_login_at = record.get("last_login_at")
            else:
                session.add(
                    UserDB(
                        id=uid,
                        email=record["email"],
                        display_name=record["display_name"],
                        role=record["role"],
                        password_hash=record["password_hash"],
                        token_version=record.get("token_version", 0),
                        locked=record.get("locked", False),
                        failed_attempts=record.get("failed_attempts", 0),
                        created_at=record.get("created_at", datetime.now(UTC).isoformat()),
                        last_login_at=record.get("last_login_at"),
                    )
                )


def db_load_devices(mode: str = "simulator") -> list[dict[str, Any]]:
    """Fetch devices for the given mode from database."""
    with get_db_session() as session:
        rows = session.query(DeviceDB).filter_by(mode=mode).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "room": r.room,
                "kind": r.kind,
                "online": r.online,
                "state": r.state or {},
                "capabilities": r.capabilities or {},
            }
            for r in rows
        ]


def db_save_devices(devices: list[dict[str, Any]], mode: str = "simulator") -> None:
    """Upsert list of devices for the given mode into database."""
    with get_db_session() as session:
        for dev in devices:
            dev_id = dev.get("id")
            if not dev_id:
                continue
            row = session.query(DeviceDB).filter_by(id=dev_id, mode=mode).first()
            if row:
                row.name = dev.get("name", row.name)
                row.room = dev.get("room", row.room)
                row.kind = dev.get("kind", row.kind)
                row.online = dev.get("online", row.online)
                row.state = dev.get("state", row.state)
                row.capabilities = dev.get("capabilities", row.capabilities)
                row.updated_at = datetime.now(UTC).isoformat()
            else:
                session.add(
                    DeviceDB(
                        id=dev_id,
                        mode=mode,
                        name=dev.get("name", "Unknown"),
                        room=dev.get("room", "Chưa phân loại"),
                        kind=dev.get("kind", "light"),
                        online=dev.get("online", True),
                        state=dev.get("state", {}),
                        capabilities=dev.get("capabilities", {}),
                        updated_at=datetime.now(UTC).isoformat(),
                    )
                )
