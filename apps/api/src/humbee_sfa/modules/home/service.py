"""Today composition — M08 §5.1 (S-HOME data assembly), epic 03 Story 3.4.

One composite read fans out, in-process, to each owning module's own public service function
(attendance, routes, approvals, notifications, identity) — never their repositories or models
directly (CLAUDE.md layer rules). Each section degrades independently: a section that raises is
caught here and turned into a typed `unavailable` discriminator, so one broken or not-yet-punched-
in section never fails the whole response. Targets is always the explicit `unavailable` shape —
see the note at its key in `get_today`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from sqlalchemy.orm import Session

from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.modules.approvals.service import ApprovalService
from humbee_sfa.modules.attendance.service import current_business_date, get_duty_state
from humbee_sfa.modules.identity.service import IdentityService
from humbee_sfa.modules.notifications.service import NotificationService
from humbee_sfa.modules.routes.service import RouteService

logger = structlog.get_logger("humbee_sfa.home")

_REQUESTS_LIMIT = 3
_NOTIFICATIONS_LIMIT = 5


def _unavailable(reason: str, *, retryable: bool = True) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason, "retryable": retryable, "as_of": None}


def _available(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "available", "data": data}


class TodayService:
    def __init__(
        self, session: Session, *, settings: Settings | None = None, clock: Clock | None = None
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()

    def get_today(self, *, claims: AccessTokenClaims) -> dict[str, Any]:
        business_date = current_business_date(self._clock, settings=self._settings)
        return {
            "business_date": business_date.isoformat(),
            "identity": self._identity_section(claims),
            "attendance": self._attendance_section(claims),
            "route": self._route_section(claims, business_date=business_date),
            "requests": self._requests_section(claims),
            "notifications": self._notifications_section(claims),
            # S-HOME's Targets section is target *progress*, so it needs an achievement figure
            # as well as a target. Setting targets has landed (`modules/targets`), reading
            # achievement has not — Humbee's capability has no agreed request shape — so there is
            # still nothing truthful to render here. Showing a target with no progress would read
            # as zero progress, which R-TGT-03 forbids.
            "targets": _unavailable("capability_not_released", retryable=False),
        }

    def _identity_section(self, claims: AccessTokenClaims) -> dict[str, Any]:
        try:
            me = IdentityService(self._session).get_me(claims=claims)
            return _available({"greeting_name": me["first_name"], "role": me["role"]})
        except Exception as exc:
            logger.warning("home_today_section_degraded", section="identity", error=type(exc).__name__)
            return _unavailable("identity_unavailable")

    def _attendance_section(self, claims: AccessTokenClaims) -> dict[str, Any]:
        try:
            duty = get_duty_state(
                self._session,
                tenant_id=claims.tenant_id,
                employee_id=claims.employee_id,
                clock=self._clock,
                settings=self._settings,
            )
            data = dict(duty)
            data["has_punched_in"] = duty["punched_in_at"] is not None
            data["locked"] = duty["punched_out_at"] is not None
            return _available(data)
        except Exception as exc:
            logger.warning("home_today_section_degraded", section="attendance", error=type(exc).__name__)
            return _unavailable("attendance_unavailable")

    def _route_section(self, claims: AccessTokenClaims, *, business_date: date) -> dict[str, Any]:
        try:
            data = RouteService(self._session, settings=self._settings, clock=self._clock).get_day(
                claims=claims, business_date=business_date
            )
            return _available(data)
        except ApiError as exc:
            logger.warning("home_today_section_degraded", section="route", error=exc.code)
            return _unavailable("route_unavailable")
        except Exception as exc:
            logger.warning("home_today_section_degraded", section="route", error=type(exc).__name__)
            return _unavailable("route_unavailable")

    def _requests_section(self, claims: AccessTokenClaims) -> dict[str, Any]:
        try:
            data = ApprovalService(self._session, settings=self._settings, clock=self._clock).list_mine(
                claims=claims, cursor=None, limit=_REQUESTS_LIMIT
            )
            return _available(data)
        except Exception as exc:
            logger.warning("home_today_section_degraded", section="requests", error=type(exc).__name__)
            return _unavailable("requests_unavailable")

    def _notifications_section(self, claims: AccessTokenClaims) -> dict[str, Any]:
        try:
            data = NotificationService(self._session, clock=self._clock).list_feed(
                claims=claims, cursor=None, limit=_NOTIFICATIONS_LIMIT
            )
            return _available(data)
        except Exception as exc:
            logger.warning(
                "home_today_section_degraded", section="notifications", error=type(exc).__name__
            )
            return _unavailable("notifications_unavailable")
