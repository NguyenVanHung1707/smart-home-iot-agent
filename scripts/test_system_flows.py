#!/usr/bin/env python3
"""Comprehensive end-to-end operational flow test script for Homing Hub."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx

BASE_URL = "http://localhost:8000"
SIMULATOR_URL = "http://localhost:8001"
PUBLIC_URL = "https://lophocso.io.vn"

ADMIN_EMAIL = "admin@homing.dev"
ADMIN_PASSWORD = "admin123456"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(title: str):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def print_result(flow_name: str, passed: bool, details: str = ""):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"  {status} {flow_name} {f'- {details}' if details else ''}")


async def main():
    print(f"{BOLD}====================================================={RESET}")
    print(f"{BOLD}    KIỂM THỬ CÁC LUỒNG HOẠT ĐỘNG TOÀN DIỆN - HOMING HUB{RESET}")
    print(f"{BOLD}====================================================={RESET}")

    results = []

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        # ----------------------------------------------------------------------
        # LUỒNG 1: Kiểm tra Sức khỏe Hệ thống & Kết nối Mạng
        # ----------------------------------------------------------------------
        print_step("LUỒNG 1: Kiểm tra Sức khỏe Dịch vụ & Kết nối Mạng (Health Check)")

        # 1.1 Local Backend
        try:
            res = await client.get(f"{BASE_URL}/health")
            ok = res.status_code == 200 and res.json().get("status") == "ok"
            print_result("Local Backend API (:8000/health)", ok, f"status={res.status_code}, body={res.text.strip()}")
            results.append(("Local Backend Health", ok))
        except Exception as e:
            print_result("Local Backend API (:8000/health)", False, str(e))
            results.append(("Local Backend Health", False))

        # 1.2 Device Simulator
        try:
            res = await client.get(f"{SIMULATOR_URL}/health")
            ok = res.status_code == 200
            print_result("Device Simulator (:8001/health)", ok, f"status={res.status_code}")
            results.append(("Device Simulator Health", ok))
        except Exception as e:
            print_result("Device Simulator (:8001/health)", False, str(e))
            results.append(("Device Simulator Health", False))

        # 1.3 Public Domain qua Cloudflare Tunnel
        try:
            res = await client.get(f"{PUBLIC_URL}/health")
            ok = res.status_code == 200 and res.json().get("status") == "ok"
            print_result("Cloudflare Tunnel Public Domain (lophocso.io.vn/health)", ok, f"status={res.status_code}")
            results.append(("Public Domain Health", ok))
        except Exception as e:
            print_result("Cloudflare Tunnel Public Domain (lophocso.io.vn/health)", False, str(e))
            results.append(("Public Domain Health", False))

        # ----------------------------------------------------------------------
        # LUỒNG 2: Xác thực & Quản lý Phiên Người dùng (Authentication Flow)
        # ----------------------------------------------------------------------
        print_step("LUỒNG 2: Xác thực & Quản lý Phiên Người dùng (JWT Authentication)")

        auth_headers = {}
        try:
            login_res = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            )
            ok = login_res.status_code == 200

            if ok:
                token_data = login_res.json()
                token = token_data.get("access_token")
                auth_headers = {"Authorization": f"Bearer {token}"}
                print_result("Đăng nhập Admin (admin@homing.dev)", True, f"Token type: {token_data.get('token_type')}")

                # Verify current user
                me_res = await client.get(f"{BASE_URL}/api/v1/auth/me", headers=auth_headers)
                me_ok = me_res.status_code == 200
                user_email = me_res.json().get("email") if me_ok else "unknown"
                print_result("Xác minh danh tính (/auth/me)", me_ok, f"User: {user_email}")
                results.append(("User Auth & Token Lifecycle", me_ok))
            else:
                print_result("Đăng nhập Admin", False, f"Status={login_res.status_code}: {login_res.text}")
                results.append(("User Auth & Token Lifecycle", False))
        except Exception as e:
            print_result("Đăng nhập Admin", False, str(e))
            results.append(("User Auth & Token Lifecycle", False))

        # ----------------------------------------------------------------------
        # LUỒNG 3: Quản lý Thiết bị & Đồng bộ Trạng thái (Device Registry & Control)
        # ----------------------------------------------------------------------
        print_step("LUỒNG 3: Danh mục Thiết bị & Điều khiển Trạng thái (Device State Flow)")

        try:
            # 3.1 Danh sách thiết bị
            dev_res = await client.get(f"{BASE_URL}/api/v1/devices", headers=auth_headers)
            dev_ok = dev_res.status_code == 200
            devices = dev_res.json() if dev_ok else []
            count = len(devices) if isinstance(devices, list) else 0
            print_result("Lấy danh mục thiết bị (/devices)", dev_ok, f"Tổng cộng {count} thiết bị")

            # 3.2 Cập nhật trạng thái thiết bị (ví dụ living-light)
            target_id = "living-light"
            cmd_res = await client.put(
                f"{BASE_URL}/api/v1/devices/{target_id}",
                headers=auth_headers,
                json={"state": {"power": True, "brightness": 90}},
            )
            cmd_ok = cmd_res.status_code == 200
            print_result(f"Gửi lệnh cập nhật trạng thái '{target_id}'", cmd_ok, f"Status={cmd_res.status_code}")


            # 3.3 Đọc lại trạng thái để xác minh đã đồng bộ
            get_dev_res = await client.get(f"{BASE_URL}/api/v1/devices/{target_id}", headers=auth_headers)
            updated_dev = get_dev_res.json() if get_dev_res.status_code == 200 else {}
            state = updated_dev.get("state", {})
            state_ok = state.get("power") is True
            print_result(f"Xác minh trạng thái xác nhận của '{target_id}'", state_ok, f"State: {state}")
            results.append(("Device Query & Mutation Flow", dev_ok and cmd_ok and state_ok))
        except Exception as e:
            print_result("Quản lý & Điều khiển Thiết bị", False, str(e))
            results.append(("Device Query & Mutation Flow", False))

        # ----------------------------------------------------------------------
        # LUỒNG 4: Trợ lý AI Điều khiển Bằng Tiếng Việt (AI & NLU Flow)
        # ----------------------------------------------------------------------
        print_step("LUỒNG 4: Trợ lý AI Xử lý Ngôn ngữ Tự nhiên Tiếng Việt (AI Agent Flow)")

        try:
            chat_payload = {
                "transcript": "Bật đèn phòng khách và chỉnh độ sáng 80%",
                "session_id": "flow-test-session",
            }
            ai_res = await client.post(f"{BASE_URL}/api/v1/voice/process", headers=auth_headers, json=chat_payload)
            ai_ok = ai_res.status_code == 200
            if ai_ok:
                ai_data = ai_res.json()
                reply = ai_data.get("response", "")
                plan = ai_data.get("plan", [])
                engine = ai_data.get("ai_engine", "")
                print_result(
                    "Xử lý lệnh giọng nói/văn bản tiếng Việt",
                    True,
                    f"Engine: {engine} | Phản hồi: '{reply[:60]}...' | Kế hoạch: {len(plan)} lệnh",
                )
                results.append(("AI Natural Language Control Flow", True))
            else:
                print_result("Trợ lý AI Tiếng Việt", False, f"Status={ai_res.status_code}: {ai_res.text}")
                results.append(("AI Natural Language Control Flow", False))
        except Exception as e:
            print_result("Trợ lý AI Tiếng Việt", False, str(e))
            results.append(("AI Natural Language Control Flow", False))

        # ----------------------------------------------------------------------
        # LUỒNG 5: Tích hợp Home Assistant MQTT Discovery
        # ----------------------------------------------------------------------
        print_step("LUỒNG 5: Tích hợp Khám phá Home Assistant (HA Discovery Flow)")

        try:
            ha_res = await client.post(f"{BASE_URL}/api/v1/integrations/homeassistant/sync", headers=auth_headers)
            ha_ok = ha_res.status_code == 200
            if ha_ok:
                ha_data = ha_res.json()
                dev_count = ha_data.get("device_count", 0)
                entities = ha_data.get("entities_published", 0)
                print_result(
                    "Đồng bộ Home Assistant Discovery",
                    True,
                    f"Thiết bị: {dev_count} | Thực thể MQTT xuất bản: {entities}",
                )
                results.append(("Home Assistant MQTT Discovery Flow", True))
            else:
                print_result("Đồng bộ Home Assistant Discovery", False, f"Status={ha_res.status_code}")
                results.append(("Home Assistant MQTT Discovery Flow", False))
        except Exception as e:
            print_result("Đồng bộ Home Assistant Discovery", False, str(e))
            results.append(("Home Assistant MQTT Discovery Flow", False))

        # ----------------------------------------------------------------------
        # LUỒNG 6: Bộ nhớ Dài hạn & Sở thích Cá nhân (Long-Term Memory Flow)
        # ----------------------------------------------------------------------
        print_step("LUỒNG 6: Bộ nhớ Dài hạn & Quản lý Thói quen Cá nhân (Preferences Flow)")

        try:
            # 6.1 Lưu thói quen
            pref_data = {
                "key": "flow_test_climate",
                "value": 25,
                "category": "climate",
                "description": "Nhiệt độ yêu thích khi kiểm thử",
            }
            save_pref_res = await client.post(f"{BASE_URL}/api/v1/preferences", headers=auth_headers, json=pref_data)
            save_ok = save_pref_res.status_code == 200
            print_result("Lưu thói quen mới vào Database", save_ok, f"Key: {pref_data['key']} = {pref_data['value']}")

            # 6.2 Đọc lại danh sách thói quen
            list_pref_res = await client.get(f"{BASE_URL}/api/v1/preferences?category=climate", headers=auth_headers)
            list_ok = list_pref_res.status_code == 200
            stored_list = list_pref_res.json() if list_ok else []
            found = any(p.get("key") == "flow_test_climate" for p in stored_list)
            print_result("Tra cứu thói quen trong bộ nhớ dài hạn", found, f"Tìm thấy: {found}")

            # 6.3 Xóa dọn dẹp khóa kiểm thử
            del_res = await client.delete(f"{BASE_URL}/api/v1/preferences/flow_test_climate", headers=auth_headers)
            del_ok = del_res.status_code == 200
            print_result("Xóa dọn dẹp khóa kiểm thử", del_ok)

            results.append(("Long-Term Memory & Preferences Flow", save_ok and found and del_ok))
        except Exception as e:
            print_result("Bộ nhớ Dài hạn & Thói quen", False, str(e))
            results.append(("Long-Term Memory & Preferences Flow", False))

        # ----------------------------------------------------------------------
        # LUỒNG 7: Tự động Sao lưu Cơ sở Dữ liệu & Khắc phục Thảm họa (Backup Flow)
        # ----------------------------------------------------------------------
        print_step("LUỒNG 7: Sao lưu Cơ sở Dữ liệu & Khắc phục Thảm họa (Backup & DR Flow)")

        try:
            from pathlib import Path
            root_dir = Path(__file__).resolve().parent.parent
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))

            from scripts.backup_db import create_backup, list_backups


            archive_path = create_backup(keep=5)
            bk_ok = archive_path.is_file() and archive_path.stat().st_size > 1000
            kb = round(archive_path.stat().st_size / 1024, 1)
            print_result("Tạo bản sao lưu nén (ZIP snapshot + pg_dump)", bk_ok, f"Tệp: {archive_path.name} ({kb} KB)")

            backups = list_backups()
            list_bk_ok = len(backups) > 0
            print_result("Kiểm tra danh mục bản sao lưu trong hệ thống", list_bk_ok, f"Tổng cộng {len(backups)} bản")

            results.append(("Backup & Disaster Recovery Flow", bk_ok and list_bk_ok))
        except Exception as e:
            print_result("Sao lưu & Khắc phục Thảm họa", False, str(e))
            results.append(("Backup & Disaster Recovery Flow", False))

    # ----------------------------------------------------------------------
    # TỔNG KẾT
    # ----------------------------------------------------------------------
    print(f"\n{BOLD}====================================================={RESET}")
    print(f"{BOLD}                 KẾT QUẢ TỔNG QUAN                   {RESET}")
    print(f"{BOLD}====================================================={RESET}")
    all_passed = True
    for name, ok in results:
        status_txt = f"{GREEN}THÀNH CÔNG{RESET}" if ok else f"{RED}THẤT BẠI{RESET}"
        print(f"  • {name:<36}: {status_txt}")
        if not ok:
            all_passed = False

    print(f"{BOLD}====================================================={RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}>>> TẤT CẢ 7 LUỒNG HOẠT ĐỘNG CỦA HỆ THỐNG ĐỀU HOẠT ĐỘNG HOÀN HẢO! <<<{RESET}")
    else:
        print(f"{RED}{BOLD}>>> CÓ MỘT HOẶC NHIỀU LUỒNG GẶP LỖI - HÃY KIỂM TRA LẠI CHI TIẾT. <<<{RESET}")
    print(f"{BOLD}====================================================={RESET}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
