"""Identity authorization policies."""

from __future__ import annotations

from datetime import datetime, timedelta

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.identity.models import OtpChallenge


def authorize_manager_contact(
    challenge: OtpChallenge | None,
    challenge_id: str,
    *,
    now: datetime,
    ttl_seconds: int,
) -> None:
    if challenge is None or challenge.id != challenge_id:
        raise ApiError(404, "not_found", "Manager contact is unavailable.")
    if challenge.consumed_at is None or challenge.employee_id is None:
        raise ApiError(404, "not_found", "Manager contact is unavailable.")
    if challenge.consumed_at + timedelta(seconds=ttl_seconds) < now:
        raise ApiError(404, "not_found", "Manager contact is unavailable.")
