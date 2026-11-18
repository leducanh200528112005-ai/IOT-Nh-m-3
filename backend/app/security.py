"""Optional API-key guard and thread-safe sliding-window rate limiter."""
from collections import defaultdict, deque
import secrets
import threading
import time

from fastapi import Header, Request


def verify_admin_key(settings, x_api_key: str | None = Header(default=None)):
    """Enforce X-API-Key header when ADMIN_API_KEY is configured in settings."""
    configured = settings.admin_api_key.get_secret_value().strip()
    if not configured:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, configured):
        from app.routing import RoutingError

        raise RoutingError("UNAUTHORIZED", "Thiếu hoặc sai mã API quản trị (X-API-Key).", 401)


class SlidingWindowLimiter:
    """Thread-safe per-client sliding-window rate limiter (60s window)."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, request: Request):
        if self.max_per_minute <= 0:
            return
        client_host = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        key = forwarded or client_host
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_per_minute:
                from app.routing import RoutingError

                raise RoutingError(
                    "ROUTING_RATE_LIMITED",
                    f"Vượt quá giới hạn {self.max_per_minute} lượt tìm đường/phút. Vui lòng thử lại sau.",
                    429,
                )
            bucket.append(now)
