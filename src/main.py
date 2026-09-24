import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth_routes import router as auth_router
from src.api.deps import current_user
from src.api.routes import router
from src.config import get_settings
from src.middleware.rate_limit import RateLimitMiddleware
from src.services.mqtt import start_mqtt, stop_mqtt
from src.services.speech import get_speech_runtime
from src.services.users import users


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    try:
        from src.database import init_db
        init_db()
        users.load()
    except Exception as e:
        print(f"Database initialization error: {e}")
    bootstrap_password = users.bootstrap_admin(settings)
    if bootstrap_password:
        print(f"Bootstrap admin created: {settings.bootstrap_admin_email} password={bootstrap_password}")
    start_mqtt()
    if settings.voice_enabled:
        await asyncio.to_thread(get_speech_runtime().preload)
    yield
    stop_mqtt()
    print("Shutting down...")


app = FastAPI(
    title="Homing Hub API",
    description="Vietnamese voice-first smart home hub with local AI",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    RateLimitMiddleware,
    max_ai_concurrent=settings.ai_max_concurrent,
    max_ai_queue=settings.ai_queue_capacity,
    queue_timeout_seconds=settings.ai_queue_timeout_seconds,
    max_requests_per_minute=settings.rate_limit_per_minute,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(router, prefix="/api/v1", dependencies=[Depends(current_user)])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
