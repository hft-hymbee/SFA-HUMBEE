"""Per-request correlation id and structured access logging."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"

logger = structlog.get_logger("humbee_sfa.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, binds it into structlog context, and logs one
    line per request at the boundary — never per-route, never per-row."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started_at = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)

        response.headers[REQUEST_ID_HEADER] = request_id
        log = logger.warning if response.status_code >= 400 else logger.info
        log(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


def get_request_id(request: Request) -> str | None:
    """Fetch the current request's correlation id, e.g. to stamp onto an audit row."""

    return getattr(request.state, "request_id", None)
