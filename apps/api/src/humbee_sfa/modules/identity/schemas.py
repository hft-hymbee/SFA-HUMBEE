"""Identity HTTP request and response DTOs.

Validation lives here, at the API boundary: the fixed `+91` country code, the
6-digit-class OTP, and the `purpose` / `platform` enums.
Unknown enum values and malformed identifiers are rejected rather than normalised
silently; case is the only thing normalised, because the wire contract is uppercase
(`LOGIN`, `WEB_PWA`) while the tables store lowercase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Fixed-country E.164 — `+91` followed by exactly ten digits.
PHONE_E164_PATTERN = r"^\+91\d{10}$"
# ULID (Crockford base32), the identifier shape of every SFA row.
ULID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"
# The code is digits only; its exact length is runtime config
# (`otp_length`, 4–8), so the boundary validates the class, not a hard-coded 6.
OTP_CODE_PATTERN = r"^\d{4,8}$"

OtpPurpose = Literal["login", "reauth"]
DevicePlatform = Literal["web_pwa", "android", "ios"]


def _lower(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


def _strip(value: Any) -> Any:
    """Drop every whitespace character — clients format phones and OTPs for humans."""

    return "".join(value.split()) if isinstance(value, str) else value


class OtpRequestBody(BaseModel):
    phone_e164: str | None = Field(default=None, pattern=PHONE_E164_PATTERN)
    purpose: OtpPurpose
    client_device_id: str = Field(min_length=1, max_length=255)

    @field_validator("purpose", mode="before")
    @classmethod
    def _normalise_purpose(cls, value: Any) -> Any:
        return _lower(value)

    @field_validator("phone_e164", mode="before")
    @classmethod
    def _normalise_phone(cls, value: Any) -> Any:
        return _strip(value)

    @model_validator(mode="after")
    def require_phone_for_login(self) -> OtpRequestBody:
        # `phone_e164` is required for LOGIN and omitted for REAUTH, where the
        # number is taken from the device's existing session instead.
        if self.purpose == "login" and self.phone_e164 is None:
            raise ValueError("phone_e164 is required for a login OTP")
        return self


class OtpRequestResponse(BaseModel):
    challenge_id: str
    phone_e164: str
    resend_available_at: datetime
    expires_at: datetime


class OtpVerifyBody(BaseModel):
    challenge_id: str = Field(pattern=ULID_PATTERN)
    code: str = Field(pattern=OTP_CODE_PATTERN)
    purpose: OtpPurpose
    client_device_id: str = Field(min_length=1, max_length=255)
    platform: DevicePlatform
    app_version: str = Field(min_length=1, max_length=64)

    @field_validator("purpose", "platform", mode="before")
    @classmethod
    def _normalise_enums(cls, value: Any) -> Any:
        return _lower(value)

    @field_validator("code", mode="before")
    @classmethod
    def _normalise_code(cls, value: Any) -> Any:
        return _strip(value)


class MeResponse(BaseModel):
    id: str
    first_name: str
    full_name: str
    phone_e164: str
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    profile: dict[str, Any] | None = None


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)
    client_device_id: str = Field(min_length=1, max_length=255)


class LogoutBody(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)


class ManagerContactResponse(BaseModel):
    manager_name: str
    manager_phone_e164: str


class SessionIntrospectResponse(BaseModel):
    device_id: str
    issued_at: datetime
    access_token_expires_at: datetime
    platform: str


class AuthConfigResponse(BaseModel):
    otp_length: int
    resend_cooldown_seconds: int
    otp_ttl_seconds: int
    max_attempts: int
