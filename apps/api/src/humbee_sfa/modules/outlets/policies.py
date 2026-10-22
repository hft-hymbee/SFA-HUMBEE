"""Outlets authorization policies."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.outlets.models.owner_otp_challenge import OwnerOtpChallenge

MIN_OWNER_AGE_YEARS = 14


def authorize_owner_date_of_birth(date_of_birth: date | None, *, now: datetime) -> None:
    if date_of_birth is None:
        return
    today = now.date()
    if date_of_birth > today:
        raise ApiError(422, "date_of_birth_invalid", "Date of birth cannot be in the future.")
    age_years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age_years -= 1
    if age_years < MIN_OWNER_AGE_YEARS:
        raise ApiError(
            422,
            "date_of_birth_invalid",
            f"The owner must be at least {MIN_OWNER_AGE_YEARS} years old.",
        )


def authorize_owner_phone_verified(
    challenge: OwnerOtpChallenge | None,
    *,
    phone_hmac: str,
    now: datetime,
    ttl_seconds: int,
) -> None:
    if challenge is None or challenge.consumed_at is None or challenge.phone_e164_hmac != phone_hmac:
        raise ApiError(409, "owner_phone_not_verified", "Verify the owner's phone number first.")
    if challenge.consumed_at + timedelta(seconds=ttl_seconds) < now:
        raise ApiError(409, "owner_phone_not_verified", "Phone verification has expired; verify again.")
