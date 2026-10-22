"""The one HTTP client through which every Humbee call passes.

Every response is HTTP 200, even on failure — the real outcome is an envelope:
`{ message, error, error_code, data, formatting_args }`. Success is `error == false` and
`error_code == "000"`; HTTP status carries no signal.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Mapping
from typing import Any

import httpx
import structlog

from humbee_sfa.core.settings import Settings

logger = structlog.get_logger("humbee_sfa.humbee_client")

_DEFAULT_TIMEOUT_S = 30.0


class HumbeeError(RuntimeError):
    def __init__(
        self, message: str, *, error_code: str | None, corr_id: str | None, retryable: bool
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.corr_id = corr_id
        self.retryable = retryable


class HumbeeAuthError(HumbeeError):
    pass


class HumbeeNotFoundError(HumbeeError):
    pass


class HumbeeBadRequestError(HumbeeError):
    pass


class HumbeeUpstreamFault(HumbeeError):
    pass


class HumbeeUnknownError(HumbeeError):
    pass


class HumbeeTransportError(HumbeeError):
    pass


class HumbeeAlreadyRegisteredError(HumbeeError):
    pass


class HumbeeInvalidDocumentFormatError(HumbeeError):
    pass


class HumbeeRefusedError(HumbeeError):
    pass


_ERROR_CODE_EXCEPTIONS: dict[str, type[HumbeeError]] = {
    "002": HumbeeAuthError,
    "030": HumbeeNotFoundError,
    "998": HumbeeBadRequestError,
    "999": HumbeeUpstreamFault,
    # SFA - onboarding (ON-1..ON-4), SFA-API-Contract v2.2 §4A/§8 — unique to this section.
    # Verified against api-dev.humbee.in: the verify endpoint's already-registered response is 088,
    # and the document-lookup endpoint returns 090 for a GSTIN or PAN whose firm already exists.
    "088": HumbeeAlreadyRegisteredError,  # phone number already has a Humbee account
    "089": HumbeeBadRequestError,  # malformed or missing phone_number on the verify endpoint
    "090": HumbeeAlreadyRegisteredError,  # document/firm already exists in Humbee
    "091": HumbeeBadRequestError,  # missing gstin and pan on the document-lookup endpoint
    "092": HumbeeInvalidDocumentFormatError,  # GSTIN/PAN pattern is malformed
    "093": HumbeeInvalidDocumentFormatError,  # (as above)
    # ON-1: the GSTIN/PAN is well-formed but no record resolves upstream. A dead end for this
    # document, not an outage — the caller gets 404, not 503.
    "094": HumbeeNotFoundError,
    "099": HumbeeRefusedError,  # document does not verify, or a replayed write is refused
    # G-3/G-4: a zone_ids/state_ids value is not an integer. An unknown but well-formed id is not
    # an error (contributes no group), so this is only the malformed case.
    "041": HumbeeBadRequestError,
}

_RETRYABLE_ERROR_CODES = {"999"}


def _sleep_with_jitter(attempt: int) -> None:
    base = min(0.25 * (2**attempt), 2.0)
    time.sleep(base + random.uniform(0, base * 0.25))


class HumbeeClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.humbee_base_url:
            raise RuntimeError("humbee_base_url is not configured for this environment")
        if not settings.humbee_api_key:
            raise RuntimeError("HUMBEE_API_KEY is not set for this environment")
        self._base_url = settings.humbee_base_url.rstrip("/")
        self._api_key = settings.humbee_api_key
        self._http = httpx.Client(limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))

    def close(self) -> None:
        self._http.close()

    def call(
        self,
        capability: str,
        method: str,
        path: str,
        *,
        route: str | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_retries: int = 1,
        idempotency_key: str | None = None,
    ) -> Any:
        # capability/route are log fields only (dotted id, path template) — never a real id.
        headers = {"api-key": self._api_key}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        attempt = 0
        while True:
            try:
                result = self._attempt(
                    method=method,
                    path=path,
                    headers=headers,
                    params=params,
                    json_body=json_body,
                    timeout_s=timeout_s,
                )
            except HumbeeError as exc:
                if exc.retryable and attempt < max_retries:
                    attempt += 1
                    _sleep_with_jitter(attempt)
                    continue

                self._log_outcome(
                    capability=capability,
                    route=route or path,
                    method=method,
                    outcome="failed",
                    error_code=exc.error_code,
                    corr_id=exc.corr_id,
                    attempts=attempt + 1,
                )
                raise

            self._log_outcome(
                capability=capability,
                route=route or path,
                method=method,
                outcome="success",
                error_code="000",
                corr_id=None,
                attempts=attempt + 1,
            )
            return result

    def _attempt(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        params: Mapping[str, Any] | None,
        json_body: Mapping[str, Any] | None,
        timeout_s: float,
    ) -> Any:
        try:
            response = self._http.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                json=json_body,
                headers=headers,
                timeout=timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise HumbeeTransportError(
                "Humbee call timed out", error_code=None, corr_id=None, retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise HumbeeTransportError(
                "Humbee call failed before a response was received",
                error_code=None,
                corr_id=None,
                retryable=True,
            ) from exc

        if response.status_code != httpx.codes.OK:
            raise HumbeeTransportError(
                f"unexpected HTTP status {response.status_code}",
                error_code=None,
                corr_id=None,
                retryable=True,
            )

        body = response.json()
        if body.get("error") is False and body.get("error_code") == "000":
            return body.get("data")

        error_code = str(body.get("error_code") or "")
        data = body.get("data")
        corr_id = data.get("corr_id") if isinstance(data, dict) else None
        exc_cls = _ERROR_CODE_EXCEPTIONS.get(error_code, HumbeeUnknownError)
        retryable = error_code in _RETRYABLE_ERROR_CODES
        raise exc_cls(
            body.get("message") or "Humbee call failed",
            error_code=error_code,
            corr_id=corr_id,
            retryable=retryable,
        )

    def _log_outcome(
        self,
        *,
        capability: str,
        route: str,
        method: str,
        outcome: str,
        error_code: str | None,
        corr_id: str | None,
        attempts: int,
    ) -> None:
        log = logger.info if outcome == "success" else logger.warning
        log(
            "humbee_call",
            capability=capability,
            route=route,
            method=method,
            outcome=outcome,
            error_code=error_code,
            corr_id=corr_id,
            attempts=attempts,
        )


_client: HumbeeClient | None = None
_client_lock = threading.Lock()


def get_humbee_client(settings: Settings) -> HumbeeClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = HumbeeClient(settings)
    return _client


def reset_humbee_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
        _client = None
