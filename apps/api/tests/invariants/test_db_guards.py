from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.conftest import NOW
from tests.fixtures import seed

from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import HardDeleteNotAllowedError
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.approvals.models import Request
from humbee_sfa.modules.approvals.service import ApprovalService
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.routes.models import RouteVisit

TODAY = date(2026, 10, 19)


def test_hard_delete_is_refused(db_session: Session) -> None:
    employee = seed.employee(db_session, "sales_person")

    db_session.delete(employee)
    with pytest.raises(HardDeleteNotAllowedError):
        db_session.flush()
    db_session.rollback()


def _approval(requester: Employee, approver: Employee, subject_id: str, status: str) -> Request:
    return Request(
        tenant_id=requester.tenant_id,
        subject_type="leave",
        subject_id=subject_id,
        requester_id=requester.id,
        requester_manager_id=approver.id,
        assigned_approver_id=approver.id,
        routing_reason="direct_parent",
        status=status,
        title="Leave",
        subtitle="Casual",
        submitted_at=NOW,
        submitted_business_date=TODAY,
        decided_at=None if status == "pending" else NOW,
    )


def test_one_pending_approval_per_subject(db_session: Session) -> None:
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    subject_id = generate_ulid()
    db_session.add_all(
        [
            _approval(sp, manager, subject_id, "approved"),
            _approval(sp, manager, subject_id, "pending"),
        ]
    )
    db_session.flush()
    pending = db_session.scalars(
        select(Request).where(Request.subject_id == subject_id, Request.status == "pending")
    ).one()

    with pytest.raises(ApiError) as duplicate:
        ApprovalService(db_session).create(
            tenant_id=sp.tenant_id, subject_type="leave", subject_id=subject_id, requester_id=sp.id
        )
    assert (duplicate.value.status_code, duplicate.value.code) == (409, "duplicate_pending_request")
    assert duplicate.value.details == {"request_id": pending.id}

    with (
        pytest.raises(IntegrityError, match="uq_approvals_one_pending_per_subject"),
        db_session.begin_nested(),
    ):
        db_session.add(_approval(sp, manager, subject_id, "pending"))


def _visit(employee_id: str, state: str) -> RouteVisit:
    return RouteVisit(
        tenant_id=seed.tenant_id(),
        employee_id=employee_id,
        humbee_outlet_id=generate_ulid(),
        state=state,
        origin="unplanned",
        visit_type="telephonic",
        checked_in_at=NOW,
        occurred_at=NOW,
        received_at=NOW,
        business_date=TODAY,
    )


def test_one_open_visit_per_employee(db_session: Session) -> None:
    employee_id = generate_ulid()
    other_id = generate_ulid()
    db_session.add_all(
        [
            _visit(employee_id, "in_progress"),
            _visit(employee_id, "visited_no_order"),
            _visit(other_id, "in_progress"),
        ]
    )
    db_session.flush()

    with pytest.raises(IntegrityError, match="ix_routes_visits_open"), db_session.begin_nested():
        db_session.add(_visit(employee_id, "in_progress"))
