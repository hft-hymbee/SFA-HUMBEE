"""Identity/auth domain event names and publish helper."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from humbee_sfa.platform.domain_events import DomainEventPublisher

OTP_REQUESTED = "otp_requested"
OTP_VERIFIED = "otp_verified"
OTP_FAILED = "otp_failed"
OTP_RATE_LIMITED = "otp_rate_limited"
LOGIN_BLOCKED_DEACTIVATED = "login_blocked_deactivated"
SESSION_CREATED = "session_created"
SESSION_REFRESHED = "session_refreshed"
REAUTH_SUCCEEDED = "reauth_succeeded"
LOGOUT = "logout"


def publish_auth_event(
    publisher: DomainEventPublisher,
    *,
    tenant_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    actor_employee_id: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    publisher.publish(
        tenant_id=tenant_id,
        stream="identity",
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        actor_employee_id=actor_employee_id,
        occurred_at=occurred_at,
    )
