"""SMS gateway abstraction."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx
import structlog

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings

logger = structlog.get_logger("humbee_sfa.sms")

OTP_SEND_MAX_RETRIES = 2
OTP_SEND_RETRY_DELAYS_SECONDS = (1.0, 2.0)
OTP_SERVER_BUSY_RETRY_AFTER_SECONDS = 5
OTP_SEND_RETRY_DELAY_CAP_SECONDS = 5.0
OTP_SEND_RETRY_JITTER_MAX_SECONDS = 0.25
_TRANSIENT_STATUS_CODES = {
    httpx.codes.TOO_MANY_REQUESTS,
    httpx.codes.BAD_GATEWAY,
    httpx.codes.SERVICE_UNAVAILABLE,
    httpx.codes.GATEWAY_TIMEOUT,
}


class SmsGateway(Protocol):
    def send_otp(self, *, phone_e164: str, code: str, purpose: str) -> None: ...


class LocalSmsGateway:
    """Non-delivering local adapter; the configured override enables manual verification."""

    def send_otp(self, *, phone_e164: str, code: str, purpose: str) -> None:
        del phone_e164, code, purpose


class TelspSmsGateway:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.otp_sms_gateway_url
        self._username = settings.otp_sms_username
        self._api_key = settings.otp_sms_api_key
        self._signature = settings.otp_sms_signature
        self._msg_type = settings.otp_sms_msg_type
        self._entity_id = settings.otp_sms_entity_id
        self._template_id = settings.otp_sms_template_id
        self._message_template = settings.otp_sms_message_template
        self._timeout_seconds = settings.otp_sms_timeout_seconds

    def send_otp(self, *, phone_e164: str, code: str, purpose: str) -> None:
        del purpose
        params = {
            "username": self._username,
            "dest": _dest_from_e164(phone_e164),
            "apikey": self._api_key,
            "signature": self._signature,
            "msgtype": self._msg_type,
            "msgtxt": self._message_template.format(otp=code),
            "entityid": self._entity_id,
            "templateid": self._template_id,
        }
        for attempt_idx in range(OTP_SEND_MAX_RETRIES + 1):
            try:
                response = httpx.get(self._url, params=params, timeout=self._timeout_seconds)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
                if attempt_idx < OTP_SEND_MAX_RETRIES:
                    time.sleep(_retry_delay_seconds(attempt_idx, retry_after_seconds=None))
                    continue
                logger.warning(
                    "otp_delivery_busy_after_retries",
                    attempts=attempt_idx + 1,
                    error_type=type(exc).__name__,
                )
                raise _otp_server_busy_error() from exc
            except httpx.HTTPError as exc:
                logger.warning("otp_delivery_failed", error_type=type(exc).__name__)
                raise ApiError(
                    503, "otp_delivery_unavailable", "OTP service is unavailable. Please try again."
                ) from exc

            if response.status_code == httpx.codes.OK:
                return

            retry_after_seconds = _retry_after_seconds(response)
            if response.status_code in _TRANSIENT_STATUS_CODES:
                if attempt_idx < OTP_SEND_MAX_RETRIES:
                    delay = _retry_delay_seconds(attempt_idx, retry_after_seconds)
                    time.sleep(delay)
                    continue
                logger.warning(
                    "otp_delivery_busy_after_retries",
                    attempts=attempt_idx + 1,
                    status_code=response.status_code,
                    retry_after_seconds=retry_after_seconds,
                )
                raise _otp_server_busy_error(retry_after_seconds=retry_after_seconds)

            logger.warning("otp_delivery_failed", status_code=response.status_code)
            raise ApiError(
                503, "otp_delivery_unavailable", "OTP service is unavailable. Please try again."
            )


def _dest_from_e164(phone_e164: str) -> str:
    # Telsp expects destination without '+' prefix, e.g., +9198.. -> 9198..
    if not phone_e164.startswith("+91"):
        raise ApiError(400, "invalid_phone", "Invalid phone number.")
    return phone_e164[1:]


def _missing_telsp_fields(settings: Settings) -> list[str]:
    missing: list[str] = []
    required = {
        "otp_sms_gateway_url": settings.otp_sms_gateway_url,
        "otp_sms_username": settings.otp_sms_username,
        "otp_sms_api_key": settings.otp_sms_api_key,
        "otp_sms_signature": settings.otp_sms_signature,
        "otp_sms_msg_type": settings.otp_sms_msg_type,
        "otp_sms_entity_id": settings.otp_sms_entity_id,
        "otp_sms_template_id": settings.otp_sms_template_id,
        "otp_sms_message_template": settings.otp_sms_message_template,
    }
    for key, value in required.items():
        if not value:
            missing.append(key)
    return missing


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        return max(int(value), 0)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    seconds = int((parsed - datetime.now(UTC)).total_seconds())
    return max(seconds, 0)


def _retry_delay_seconds(attempt_idx: int, retry_after_seconds: int | None) -> float:
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return min(float(retry_after_seconds), OTP_SEND_RETRY_DELAY_CAP_SECONDS)
    return OTP_SEND_RETRY_DELAYS_SECONDS[attempt_idx] + random.uniform(
        0.0, OTP_SEND_RETRY_JITTER_MAX_SECONDS
    )


def _otp_server_busy_error(*, retry_after_seconds: int | None = None) -> ApiError:
    value = (
        min(retry_after_seconds, int(OTP_SEND_RETRY_DELAY_CAP_SECONDS))
        if retry_after_seconds is not None and retry_after_seconds > 0
        else OTP_SERVER_BUSY_RETRY_AFTER_SECONDS
    )
    return ApiError(
        503,
        "otp_server_busy",
        "OTP server is busy. Please retry after a few seconds.",
        details={"retry_after_seconds": value},
    )


def get_sms_gateway(settings: Settings) -> SmsGateway:
    missing = _missing_telsp_fields(settings)
    if not missing:
        return TelspSmsGateway(settings)

    if settings.environment in {"local", "test"} or settings.otp_skip_verification:
        logger.warning(
            "sms_gateway_local_fallback",
            environment=settings.environment,
            missing_fields=missing,
        )
        return LocalSmsGateway()

    raise RuntimeError(
        f"SMS gateway configuration is incomplete for environment '{settings.environment}'. "
        f"Missing: {', '.join(missing)}"
    )
