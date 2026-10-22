"""Global exception handling.

Every error a request can surface — a raised HTTPException, a request-validation
failure, or an unhandled bug — is converted here into one structured JSON
envelope and logged exactly once at the right level. Route code never needs its
own try/except for this; it either returns normally or raises.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import structlog
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from humbee_sfa.platform.telemetry.middleware import REQUEST_ID_HEADER, get_request_id

logger = structlog.get_logger("humbee_sfa.errors")

# Validation errors carry the submitted field value in `input`; strip it for
# any field that may hold PII/secrets before it is logged or echoed back.
_SENSITIVE_FIELD_MARKERS = {
    "phone",
    "phone_number",
    "phone_e164",
    "otp",
    "otp_code",
    "code",  # the OTP verify body field: never echoed, never logged
    "refresh_token",
    "password",
    "token",
    "gps",
    "latitude",
    "longitude",
    "gst",
    "gstin",
    "pan",
}


class ApiError(StarletteHTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: Mapping[str, str] | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.details = details


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def _sanitize_validation_errors(errors: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        loc_parts = {str(part).lower() for part in error.get("loc", ())}
        clean = dict(error)
        if loc_parts & _SENSITIVE_FIELD_MARKERS:
            clean.pop("input", None)
            clean.pop("ctx", None)
        # A model validator's `ctx` carries the raised exception itself, and `input`
        # can be any submitted object; neither is guaranteed JSON-serializable.
        if "ctx" in clean:
            ctx = clean["ctx"]
            clean["ctx"] = (
                {key: _json_safe(item) for key, item in ctx.items()}
                if isinstance(ctx, Mapping)
                else _json_safe(ctx)
            )
        # A model-level error echoes the whole submitted body, phone number included.
        if "input" in clean and not isinstance(clean["input"], (str, int, float, bool, type(None))):
            clean.pop("input")
        sanitized.append(clean)
    return sanitized


def _envelope(code: str, message: str, request_id: str | None, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _request_id_headers(
    request_id: str | None, extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    # Starlette routes bare-Exception handlers onto the outermost ServerErrorMiddleware,
    # outside RequestContextMiddleware's reach, so every handler stamps the header itself
    # rather than relying on that middleware to do it after the fact.
    headers = dict(extra or {})
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    return headers


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    request_id = get_request_id(request)
    log = logger.error if exc.status_code >= 500 else logger.warning
    code = getattr(exc, "code", f"http_{exc.status_code}")
    details = getattr(exc, "details", None)
    log("http_exception", status_code=exc.status_code, code=code, detail=exc.detail, request_id=request_id)
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(code, str(exc.detail), request_id, details=details),
        headers=_request_id_headers(request_id, exc.headers),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    request_id = get_request_id(request)
    sanitized_errors = _sanitize_validation_errors(exc.errors())
    logger.warning("validation_error", errors=sanitized_errors, request_id=request_id)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(
            "validation_error", "Request validation failed.", request_id, details=sanitized_errors
        ),
        headers=_request_id_headers(request_id),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        request_id=request_id,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope("internal_error", "An unexpected error occurred.", request_id),
        headers=_request_id_headers(request_id),
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
