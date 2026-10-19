#!/usr/bin/env python3
"""Automated Database Backup and Disaster Recovery Tool for Homing Hub."""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import shutil
import subprocess

import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT_DIR / "backups"
DATA_DIR = ROOT_DIR / "data"
RUNTIME_DIR = ROOT_DIR / "runtime"


def find_postgres_container() -> str | None:
    """Find running PostgreSQL container name."""
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--filter", "ancestor=postgres:16-alpine", "--format", "{{.Names}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if lines:
            return lines[0]

        # Fallback check by name filter
        out2 = subprocess.check_output(
            ["docker", "ps", "--filter", "name=postgres", "--format", "{{.Names}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        lines2 = [line.strip() for line in out2.splitlines() if line.strip()]
        return lines2[0] if lines2 else None
    except Exception:
        return None


def export_sqlalchemy_snapshot() -> dict[str, list[dict[str, Any]]]:
    """Export all database tables into serialized dictionary snapshot."""
    snapshot: dict[str, list[dict[str, Any]]] = {}
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from src.database import DeviceDB, UserDB, UserPreferenceDB, get_db_session

        with get_db_session() as session:
            # Users
            users = session.query(UserDB).all()
            snapshot["users"] = [
                {
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
            ]

            # Devices
            devices = session.query(DeviceDB).all()
            snapshot["devices"] = [
                {
                    "id": d.id,
                    "mode": d.mode,
                    "name": d.name,
                    "room": d.room,
                    "kind": d.kind,
                    "online": d.online,
                    "state": d.state or {},
                    "capabilities": d.capabilities or {},
                    "updated_at": d.updated_at,
                }
                for d in devices
            ]

            # User Preferences (Long-term memory)
            prefs = session.query(UserPreferenceDB).all()
            snapshot["user_preferences"] = [
                {
                    "id": p.id,
                    "user_id": p.user_id,
                    "key": p.key,
                    "value": p.value,
                    "category": p.category,
                    "description": p.description,
                    "updated_at": p.updated_at,
                }
                for p in prefs
            ]
    except Exception as e:
        logger.warning("Could not export SQLAlchemy snapshot: %s", e)
    return snapshot


def create_backup(keep: int = 7) -> Path:
    """Create a complete timestamped backup archive of database and config states."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BACKUP_DIR / f"homing_backup_{timestamp}.zip"
    temp_dir = BACKUP_DIR / f"temp_{timestamp}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        manifest: dict[str, Any] = {
            "version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "timestamp": timestamp,
            "components": [],
        }

        # 1. SQLAlchemy snapshot export
        db_snapshot = export_sqlalchemy_snapshot()
        if db_snapshot:
            db_json_path = temp_dir / "database_snapshot.json"
            db_json_path.write_text(json.dumps(db_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest["components"].append("database_snapshot.json")
            counts = {table: len(rows) for table, rows in db_snapshot.items()}
            manifest["db_counts"] = counts
            logger.info("Exported database tables: %s", counts)

        # 2. Native pg_dump if container available
        pg_container = find_postgres_container()
        if pg_container:
            sql_path = temp_dir / "homing_db.sql"
            try:
                cmd = ["docker", "exec", pg_container, "pg_dump", "-U", "homing_user", "homing_db"]
                with open(sql_path, "wb") as f:
                    subprocess.check_call(cmd, stdout=f, stderr=subprocess.DEVNULL)
                manifest["components"].append("homing_db.sql")
                logger.info("Captured native pg_dump via container '%s'", pg_container)
            except Exception as e:
                logger.warning("Native pg_dump failed: %s", e)

        # 3. Capture file snapshots from data/ and runtime/
        files_to_backup = [
            DATA_DIR / "devices.json",
            DATA_DIR / "devices_real.json",
            RUNTIME_DIR / "devices.json",
            ROOT_DIR / "infra" / "pwfile",
            ROOT_DIR / "infra" / "aclfile",
        ]
        file_copies: list[str] = []
        for fp in files_to_backup:
            if fp.exists():
                rel_name = fp.name
                dest = temp_dir / rel_name
                shutil.copy(fp, dest)
                file_copies.append(rel_name)
        manifest["files"] = file_copies

        # 4. Write manifest
        (temp_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # 5. Pack into ZIP archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for item in temp_dir.iterdir():
                zipf.write(item, arcname=item.name)

        size_kb = zip_path.stat().st_size / 1024
        logger.info("[SUCCESS] Created backup archive: %s (%.1f KB)", zip_path.name, size_kb)

        # Rotate old backups
        rotate_backups(keep=keep)
        return zip_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def rotate_backups(keep: int = 7) -> list[str]:
    """Purge backups older than the most recent `keep` archives."""
    if not BACKUP_DIR.exists():
        return []
    archives = sorted(BACKUP_DIR.glob("homing_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: list[str] = []
    if len(archives) > keep:
        for old in archives[keep:]:
            logger.info("Rotating old backup: %s", old.name)
            old.unlink(missing_ok=True)
            deleted.append(old.name)
    return deleted


def list_backups() -> list[dict[str, Any]]:
    """List all available backup archives with metadata."""
    if not BACKUP_DIR.exists():
        print("Chưa có thư mục backups/.")
        return []

    archives = sorted(BACKUP_DIR.glob("homing_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not archives:
        print("Không có bản sao lưu nào trong backups/.")
        return []

    print(f"\n--- Danh sách Bản sao lưu Homing Hub ({len(archives)} bản) ---")
    results = []
    for arch in archives:
        size_kb = arch.stat().st_size / 1024
        mtime = datetime.fromtimestamp(arch.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        info = {"filename": arch.name, "path": str(arch), "size_kb": round(size_kb, 1), "modified": mtime}

        # Inspect manifest inside archive
        try:
            with zipfile.ZipFile(arch, "r") as z:
                if "manifest.json" in z.namelist():
                    data = json.loads(z.read("manifest.json").decode("utf-8"))
                    info["db_counts"] = data.get("db_counts", {})
                    info["components"] = data.get("components", [])
        except Exception:
            pass
        results.append(info)
        counts_str = f" | DB: {info.get('db_counts')}" if "db_counts" in info else ""
        print(f"  * {arch.name:<32} {info['size_kb']:>6.1f} KB | {mtime}{counts_str}")
    return results


def restore_backup(backup_file: str | Path) -> bool:
    """Restore database and device states from a backup archive."""
    path = Path(backup_file)
    if not path.is_file():
        # Check inside BACKUP_DIR if relative
        alt_path = BACKUP_DIR / backup_file
        if alt_path.is_file():
            path = alt_path
        else:
            logger.error("Không tìm thấy tệp bản sao lưu: %s", backup_file)
            return False

    temp_dir = BACKUP_DIR / f"restore_temp_{secrets.token_hex(4)}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path, "r") as zipf:
            zipf.extractall(temp_dir)

        manifest_path = temp_dir / "manifest.json"
        if not manifest_path.exists():
            logger.error("Bản sao lưu không hợp lệ: thiếu manifest.json")
            return False

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        logger.info("Restoring backup from %s (Created: %s)...", path.name, manifest.get("created_at"))

        # 1. Restore JSON database snapshot via SQLAlchemy
        db_snapshot_path = temp_dir / "database_snapshot.json"
        if db_snapshot_path.exists():
            data = json.loads(db_snapshot_path.read_text(encoding="utf-8"))
            sys.path.insert(0, str(ROOT_DIR))
            from src.database import (
                DeviceDB,
                UserDB,
                UserPreferenceDB,
                get_db_session,
                init_db,
            )

            init_db()
            with get_db_session() as session:
                if "users" in data:
                    for u in data["users"]:
                        row = session.query(UserDB).filter_by(id=u["id"]).first()
                        if not row:
                            session.add(UserDB(**u))
                if "devices" in data:
                    for d in data["devices"]:
                        row = session.query(DeviceDB).filter_by(id=d["id"], mode=d.get("mode", "simulator")).first()
                        if row:
                            row.name = d["name"]
                            row.room = d["room"]
                            row.kind = d["kind"]
                            row.state = d["state"]
                            row.capabilities = d["capabilities"]
                        else:
                            session.add(DeviceDB(**d))
                if "user_preferences" in data:
                    for p in data["user_preferences"]:
                        row = session.query(UserPreferenceDB).filter_by(user_id=p["user_id"], key=p["key"]).first()
                        if row:
                            row.value = p["value"]
                            row.category = p["category"]
                            row.description = p.get("description", "")
                        else:
                            session.add(UserPreferenceDB(
                                user_id=p["user_id"],
                                key=p["key"],
                                value=p["value"],
                                category=p["category"],
                                description=p.get("description", ""),
                                updated_at=p.get("updated_at", datetime.now(UTC).isoformat()),
                            ))
            logger.info("[+] Đã khôi phục thành công các bảng cơ sở dữ liệu SQLAlchemy.")

        # 2. Restore file snapshots to data/ and runtime/
        for item in temp_dir.iterdir():
            if item.name == "devices.json":
                if DATA_DIR.exists():
                    shutil.copy(item, DATA_DIR / "devices.json")
                if RUNTIME_DIR.exists():
                    shutil.copy(item, RUNTIME_DIR / "devices.json")
                logger.info("[+] Đã khôi phục devices.json")
            elif item.name == "devices_real.json" and DATA_DIR.exists():
                shutil.copy(item, DATA_DIR / "devices_real.json")
                logger.info("[+] Đã khôi phục devices_real.json")

        logger.info("[SUCCESS] Khôi phục hoàn tất từ bản sao lưu: %s", path.name)
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sao lưu và phục hồi thảm họa tự động cho Homing Hub.")
    parser.add_argument("--backup", action="store_true", help="Tạo bản sao lưu mới ngay lập tức")
    parser.add_argument("--restore", type=str, help="Phục hồi từ tệp bản sao lưu (.zip)")
    parser.add_argument("--list", action="store_true", help="Liệt kê danh sách các bản sao lưu hiện có")
    parser.add_argument("--keep", type=int, default=7, help="Số lượng bản sao lưu gần nhất cần giữ lại (mặc định: 7)")

    args = parser.parse_args()

    if args.backup:
        create_backup(keep=args.keep)
    elif args.restore:
        restore_backup(args.restore)
    elif args.list:
        list_backups()
    else:
        # Default behavior: run backup and show list
        create_backup(keep=args.keep)
        list_backups()


if __name__ == "__main__":
    main()
