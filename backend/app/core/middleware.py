"""Middleware: X-Request-ID, access logging."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.ids import new_request_id
from app.core.logging import set_request_id

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = logging.getLogger("tte.access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensure every request has an X-Request-ID."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        if incoming and _REQUEST_ID_PATTERN.match(incoming):
            req_id = incoming
        else:
            req_id = new_request_id()

        set_request_id(req_id)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        response.headers["X-Request-ID"] = req_id

        # Access log — never log body or sensitive query params
        logger.info(
            "access",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status": response.status_code,
                "duration_ms": duration_ms,
                "size": response.headers.get("content-length", ""),
            },
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply security headers to every response."""

    def __init__(self, app: ASGIApp, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if self.hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
