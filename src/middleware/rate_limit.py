"""Rate limiting and concurrency control middleware."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

HEAVY_AI_ENDPOINTS = frozenset(
    {
        "/api/v1/chat",
        "/api/v1/voice/process",
        "/api/v1/voice/transcribe",
        "/api/v1/voice/synthesize",
    }
)

DEFAULT_MAX_AI_CONCURRENT = 1
DEFAULT_MAX_AI_QUEUE = 10
DEFAULT_AI_QUEUE_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_REQUESTS_PER_MINUTE = 600
DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_RETRY_AFTER_SECONDS = 5


class QueueFullError(Exception):
    """Raised when the AI request queue capacity is reached."""


class QueueTimeoutError(Exception):
    """Raised when waiting in the AI request queue times out."""


_active_rate_limit_middleware: RateLimitMiddleware | None = None


def get_active_rate_limit_middleware() -> RateLimitMiddleware | None:
    return _active_rate_limit_middleware


def clear_rate_limits() -> None:
    if _active_rate_limit_middleware is not None:
        _active_rate_limit_middleware.reset()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_ai_concurrent: int = DEFAULT_MAX_AI_CONCURRENT,
        max_ai_queue: int = DEFAULT_MAX_AI_QUEUE,
        queue_timeout_seconds: float = DEFAULT_AI_QUEUE_TIMEOUT_SECONDS,
        max_requests_per_minute: int = DEFAULT_MAX_REQUESTS_PER_MINUTE,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        retry_after_seconds: int = DEFAULT_RETRY_AFTER_SECONDS,
    ) -> None:
        super().__init__(app)
        self.max_ai_concurrent = max_ai_concurrent
        self.max_ai_queue = max_ai_queue
        self.queue_timeout_seconds = queue_timeout_seconds
        self.max_requests_per_minute = max_requests_per_minute
        self.window_seconds = window_seconds
        self.retry_after_seconds = retry_after_seconds

        self._active_ai_count = 0
        self._ai_queue: deque[asyncio.Event] = deque()
        self._ip_requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

        global _active_rate_limit_middleware
        _active_rate_limit_middleware = self

    @property
    def active_ai_count(self) -> int:
        with self._lock:
            return self._active_ai_count

    @property
    def waiting_ai_count(self) -> int:
        with self._lock:
            return len(self._ai_queue)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    def _is_heavy_endpoint(self, path: str) -> bool:
        norm_path = path.rstrip("/") if path != "/" else path
        return norm_path in HEAVY_AI_ENDPOINTS

    def _is_health_endpoint(self, path: str) -> bool:
        norm_path = path.rstrip("/") if path != "/" else path
        return norm_path == "/health"

    def _check_ip_rate_limit(self, client_ip: str, now: float) -> bool:
        with self._lock:
            bucket = self._ip_requests[client_ip]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests_per_minute:
                return False
            bucket.append(now)
            return True

    async def _acquire_ai_slot(self) -> None:
        with self._lock:
            if self._active_ai_count < self.max_ai_concurrent:
                self._active_ai_count += 1
                return

            if len(self._ai_queue) >= self.max_ai_queue:
                raise QueueFullError("AI request queue is full")

            waiter = asyncio.Event()
            self._ai_queue.append(waiter)

        try:
            await asyncio.wait_for(waiter.wait(), timeout=self.queue_timeout_seconds)
        except TimeoutError:
            with self._lock:
                if waiter.is_set():
                    self._release_ai_slot_locked()
                else:
                    try:
                        self._ai_queue.remove(waiter)
                    except ValueError:
                        pass
            raise QueueTimeoutError("AI request queue wait timed out")
        except asyncio.CancelledError:
            with self._lock:
                if waiter.is_set():
                    self._release_ai_slot_locked()
                else:
                    try:
                        self._ai_queue.remove(waiter)
                    except ValueError:
                        pass
            raise

    def _release_ai_slot_locked(self) -> None:
        while self._ai_queue:
            next_waiter = self._ai_queue.popleft()
            if not next_waiter.is_set():
                next_waiter.set()
                return
        self._active_ai_count = max(0, self._active_ai_count - 1)

    def _release_ai_slot(self) -> None:
        with self._lock:
            self._release_ai_slot_locked()

    def reset(self) -> None:
        with self._lock:
            self._ip_requests.clear()
            self._ai_queue.clear()
            self._active_ai_count = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Bypass rate limits for /health
        if self._is_health_endpoint(path):
            return await call_next(request)

        # Global per-IP rate limit check (temporarily disabled)
        # client_ip = self._get_client_ip(request)
        # now = time.monotonic()
        # if not self._check_ip_rate_limit(client_ip, now):
        #     return JSONResponse(
        #         status_code=429,
        #         content={"detail": "rate_limit_exceeded"},
        #         headers={"Retry-After": str(self.retry_after_seconds)},
        #     )

        # Heavy AI endpoint queue and concurrency limit check
        if self._is_heavy_endpoint(path):
            try:
                await self._acquire_ai_slot()
            except QueueFullError:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "queue_full"},
                    headers={"Retry-After": str(self.retry_after_seconds)},
                )
            except QueueTimeoutError:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "queue_timeout"},
                    headers={"Retry-After": str(self.retry_after_seconds)},
                )

            try:
                return await call_next(request)
            finally:
                self._release_ai_slot()

        return await call_next(request)
