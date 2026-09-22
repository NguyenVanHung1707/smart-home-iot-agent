"""Dev server chỉ chạy phần xác thực (auth).

Dùng khi muốn thử luồng landing → đăng nhập → dashboard mà chưa cần MQTT,
Zipformer STT hay Piper TTS. Frontend ở chế độ dev mặc định lấy Mock Data cho
phần thiết bị, nên chỉ cần các endpoint /api/v1/auth/* là đủ để đăng nhập.

Chạy:
    python scripts/dev_auth_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth_routes import router as auth_router
from src.config import get_settings
from src.services.users import users


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Homing Hub API (auth only)", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix="/api/v1/auth")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "auth-only"}

    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    password = users.bootstrap_admin(settings)
    admins = [item for item in users.list() if item.role == "ADMIN"]
    print("=" * 64)
    if password:
        print(f"Bootstrap admin created: {settings.bootstrap_admin_email} password={password}")
    elif admins:
        print(f"Admin dang co: {admins[0].email}")
        if settings.bootstrap_admin_password:
            print("Mat khau: lay tu BOOTSTRAP_ADMIN_PASSWORD trong .env")
    print("Auth-only dev server: http://localhost:8000/api/v1/auth")
    print("=" * 64)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
