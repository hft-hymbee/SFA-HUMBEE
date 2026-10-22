"""Structured application logging via structlog.

Configured once at process startup so every log line — from application code
or from stdlib loggers such as uvicorn's — renders as one structured event
carrying level, timestamp, environment, request context and a redacted
payload. Log at boundaries and decisions, never PII, levels mean
something.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import EventDict, Processor

from humbee_sfa.core.settings import Settings

_REDACTED = "***redacted***"

# Field names that must never reach a log sink verbatim.
_SENSITIVE_KEYS = {
    "phone",
    "phone_number",
    "phone_e164",
    "otp",
    "otp_code",
    "gps",
    "gps_fix",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "gst",
    "gstin",
    "pan",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "api-key",
    "api_key",
    "apikey",
    "contact_mobile",
    "dest",
    "msgtxt",
}


def _redact_sensitive(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog and stdlib logging for the current process.

    Call once, before the app starts serving requests.
    """

    def _add_service_context(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", "humbee-sfa-api")
        event_dict.setdefault("environment", settings.environment)
        return event_dict

    shared_processors: list[Processor] = [
        _add_service_context,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Our own request-logging middleware replaces uvicorn's access log.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = []
    uvicorn_access.propagate = False
