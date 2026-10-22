"""Resolve an approval request to the requester's direct parent.

The reporting relationship is the approval relationship: a request is assigned to the current
direct parent and remains there until decided. A requester without a parent is auto-approved.
This function is pure apart from reading the hierarchy and is called once at submission.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from humbee_sfa.modules.approvals.contracts import RoutingReason
from humbee_sfa.modules.org import service as org_service


@dataclass(frozen=True)
class RoutingOutcome:
    """The assigned approver, or an auto-approval when the requester has no parent."""

    approver_id: str | None
    routing_reason: RoutingReason
    auto_decide: bool
    direct_parent_id: str | None


def resolve_approver(session: Session, *, tenant_id: str, requester_id: str) -> RoutingOutcome:
    """Assign the direct parent; auto-approve only when no parent exists."""

    direct_parent = org_service.parent_of(session, tenant_id=tenant_id, employee_id=requester_id)

    if direct_parent is None:
        return RoutingOutcome(
            approver_id=None,
            routing_reason=RoutingReason.AUTO_TOP_OF_HIERARCHY,
            auto_decide=True,
            direct_parent_id=None,
        )

    return RoutingOutcome(
        approver_id=direct_parent,
        routing_reason=RoutingReason.DIRECT_PARENT,
        auto_decide=False,
        direct_parent_id=direct_parent,
    )


__all__ = ["RoutingOutcome", "resolve_approver"]
