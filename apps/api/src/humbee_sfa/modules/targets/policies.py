"""Targets authorisation — M13 §9, R-TGT-05/15/17.

Authorisation only. Shape validation belongs to `schemas.py`, and row scoping to `apply_scope`.
"""

from __future__ import annotations

from datetime import date

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.scope import Role, ScopeContext, is_hierarchy_member
from humbee_sfa.modules.org.service import EmployeeProjection


def authorize_target_write(scope: ScopeContext) -> None:
    """R-TGT-05 — only a Manager or an Admin sets a target. There is no self-service target UI, so
    a Sales Person is refused here rather than being silently scoped to themselves.

    This does not use `ScopeContext.can_write`, which is Admin-only: that flag governs employee
    records (R-ORG-20, "Managers read their tree and write nothing"), and setting a target for
    someone in your team is exactly the write a Manager is meant to make.
    """

    if scope.actor_role == Role.SALES_PERSON:
        raise ApiError(403, "forbidden", "Only managers and admins set targets.")


def authorize_subject(employee: EmployeeProjection) -> None:
    """Targets are set for sales people and managers in the reporting line. Admins hold no
    hierarchy seat, and a departed employee cannot hold a target.

    The employee has already been loaded under the actor's scope, so a manager reaching outside
    their tree never gets here.

    Deviation from R-TGT-17, deliberately: M13 §7 and §11.2 both say that case returns 403, and it
    returns 404. A 403 confirms the employee exists, which is exactly the probe the scoped read
    refuses to answer, and 404-for-out-of-scope is already the convention across `org` and
    `geography_service`. The refusal a Sales Person gets for *writing at all* is still a 403.
    """

    if not is_hierarchy_member(employee.role_code):
        raise ApiError(
            422,
            "target_subject_not_hierarchy_member",
            "Targets are set for sales people and managers.",
        )
    if employee.status != "active":
        raise ApiError(422, "target_subject_inactive", "That employee is no longer active.")


def authorize_period(period_month: date, *, today: date) -> None:
    """R-TGT-15 — the current or a future month. A past period is read-only: editing a target after
    the month it measured would rewrite what the achievement was compared against."""

    if period_month.day != 1:
        raise ApiError(422, "period_not_month_start", "A period is a whole calendar month.")
    if period_month < today.replace(day=1):
        raise ApiError(
            422, "period_in_the_past", "Targets can only be set for the current or a future month."
        )
