"""Request logging middleware with correlation IDs (Phase 5.3).

Every HTTP request produces one ``request_completed`` line carrying the
method, path, status, and duration, plus an ``X-Request-ID`` the client
can quote in a bug report. An incoming id from a proxy is echoed back
when it looks sane, so one id ties a frontend action, this API, and any
upstream load balancer together.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.requests")

REQUEST_ID_HEADER = "X-Request-ID"

# Health polls run every few seconds in deployment; logging each one would
# drown out the traffic that actually matters.
_EXCLUDED_PATHS = frozenset({"/api/health"})

# Correlation ids arrive from clients and proxies, so keep them printable
# and short before echoing and logging them.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


def _request_id(headers: list[tuple[bytes, bytes]]) -> str:
    """Return the caller's request id when it is safe to echo, else a new one."""

    for name, value in headers:
        if name.lower() == b"x-request-id":
            candidate = value.decode("latin-1").strip()
            if _SAFE_REQUEST_ID.fullmatch(candidate):
                return candidate
    return uuid.uuid4().hex


class RequestLoggingMiddleware:
    """Log one structured line per request and echo a correlation id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in _EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope.get("headers", []))
        # Handlers can read the id back from ``request.state.request_id``.
        scope.setdefault("state", {})["request_id"] = request_id

        started = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append(
                    (REQUEST_ID_HEADER.encode("latin-1"), request_id.encode("latin-1"))
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request_completed %s %s status=%s duration_ms=%.1f request_id=%s",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status_code or "-",
                duration_ms,
                request_id,
                extra={
                    "event": "request_completed",
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status_code or None,
                    "duration_ms": round(duration_ms, 1),
                    "request_id": request_id,
                },
            )
