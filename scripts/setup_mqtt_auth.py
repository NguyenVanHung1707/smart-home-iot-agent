#!/usr/bin/env python3
"""Mosquitto MQTT Authentication & ACL Provisioning Tool for Homing Hub."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

INFRA_DIR = Path(__file__).resolve().parent.parent / "infra"

PWFILE_PATH = INFRA_DIR / "pwfile"
ACLFILE_PATH = INFRA_DIR / "aclfile"
ACL_EXAMPLE_PATH = INFRA_DIR / "aclfile.example"


def _generate_mosquitto_hash(password: str) -> str:
    """Generate SHA512-based hashed password for Mosquitto."""
    salt = secrets.token_bytes(16)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    derived = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, 10000)
    derived_b64 = base64.b64encode(derived).decode("ascii")
    return f"$7$10000${salt_b64}${derived_b64}"


def find_mqtt_container() -> str | None:
    """Find running mosquitto container name."""
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--filter", "ancestor=eclipse-mosquitto:2", "--format", "{{.Names}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        return lines[0] if lines else None
    except Exception:
        return None


def add_user_via_docker(container_name: str, username: str, password: str) -> bool:
    """Add or update an MQTT user using mosquitto_passwd in container."""
    try:
        cmd = ["docker", "exec", "-i", container_name, "mosquitto_passwd", "-b", "/mosquitto/config/pwfile", username, password]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Warning: docker exec mosquitto_passwd failed: {e}")
        return False


def add_user_local(username: str, password: str) -> None:
    """Fallback: append user to local pwfile."""
    INFRA_DIR.mkdir(parents=True, exist_ok=True)
    entry = f"{username}:{_generate_mosquitto_hash(password)}\n"
    existing_lines = []
    if PWFILE_PATH.exists():
        existing_lines = [l for l in PWFILE_PATH.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{username}:")]
    existing_lines.append(entry.strip())
    PWFILE_PATH.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def ensure_acl_file() -> None:
    """Ensure aclfile exists, copying from aclfile.example if missing."""
    if not ACLFILE_PATH.exists() and ACL_EXAMPLE_PATH.exists():
        shutil.copy(ACL_EXAMPLE_PATH, ACLFILE_PATH)
        print(f"[+] Created {ACLFILE_PATH} from example template.")


def init_default_accounts() -> dict[str, str]:
    """Initialize standard accounts: homing_backend, esp32_device, homing_viewer."""
    ensure_acl_file()
    container = find_mqtt_container()

    accounts = {
        "homing_backend": secrets.token_hex(16),
        "esp32_device": secrets.token_hex(12),
        "homing_viewer": secrets.token_hex(12),
    }

    print("\n--- Khởi tạo tài khoản MQTT an toàn cho Homing Hub ---")
    for user, pwd in accounts.items():
        added = False
        if container:
            added = add_user_via_docker(container, user, pwd)
        if not added:
            add_user_local(user, pwd)
        print(f"  User: {user:<16} Password: {pwd}")

    print("\n[+] Đã lưu vào infra/pwfile.")
    print("[*] Để kích hoạt chế độ xác thực trong Docker, cập nhật docker-compose.yml:")
    print("      volumes:")
    print("        - ./infra/mosquitto.auth.conf:/mosquitto/config/mosquitto.conf:ro")
    print("        - ./infra/pwfile:/mosquitto/config/pwfile:ro")
    print("        - ./infra/aclfile:/mosquitto/config/aclfile:ro")
    return accounts


def check_status() -> None:
    """Display status of MQTT auth files."""
    print("--- Trạng thái cấu hình Mosquitto Auth & ACL ---")
    print(f"  Cấu hình Auth:    {'[TỒN TẠI]' if (INFRA_DIR / 'mosquitto.auth.conf').exists() else '[CHƯA CÓ]'}")
    print(f"  Tệp Password:     {'[TỒN TẠI]' if PWFILE_PATH.exists() else '[CHƯA CÓ]'}")
    print(f"  Tệp ACL:          {'[TỒN TẠI]' if ACLFILE_PATH.exists() else '[CHƯA CÓ]'}")
    container = find_mqtt_container()
    print(f"  Container MQTT:   {container or '[KHÔNG TÌM THẤY TRỰC TIẾP]'}")
    if PWFILE_PATH.exists():
        users = [line.split(":")[0] for line in PWFILE_PATH.read_text(encoding="utf-8").splitlines() if ":" in line]
        print(f"  Các User hiện có: {', '.join(users) if users else '(trống)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quản lý xác thực và phân quyền (ACL) Mosquitto MQTT.")
    parser.add_argument("--init-defaults", action="store_true", help="Khởi tạo các tài khoản tiêu chuẩn với mật khẩu ngẫu nhiên an toàn")
    parser.add_argument("--add-user", type=str, help="Tên tài khoản cần thêm")
    parser.add_argument("--password", type=str, help="Mật khẩu của tài khoản")
    parser.add_argument("--status", action="store_true", help="Kiểm tra trạng thái cấu hình auth và ACL")

    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.init_defaults:
        init_default_accounts()
    elif args.add_user:
        pwd = args.password or secrets.token_hex(16)
        ensure_acl_file()
        container = find_mqtt_container()
        added = False
        if container:
            added = add_user_via_docker(container, args.add_user, pwd)
        if not added:
            add_user_local(args.add_user, pwd)
        print(f"[+] Đã thêm user '{args.add_user}' với mật khẩu: {pwd}")
    else:
        check_status()
        print("\nDùng --init-defaults để tạo tài khoản mặc định, hoặc --add-user <user> --password <pass>.")


if __name__ == "__main__":
    main()
