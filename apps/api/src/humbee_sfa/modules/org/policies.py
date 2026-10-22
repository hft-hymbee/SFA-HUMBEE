"""Org role-capability checks.

Capability ("may this role do this at all") is deliberately separate from scope ("which rows").
Folding them together is what turns "a Manager can see it" into "a Manager can change it".
"""

from __future__ import annotations

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org.scope import Scope, ScopeContext


def require_employee_write(context: ScopeContext) -> None:
    """Only Admin creates, edits or deactivates an employee."""

    if not context.can_write or context.scope is not Scope.ORG:
        raise ApiError(403, "forbidden", "Employee changes are Admin-only.")


def require_hierarchy_mutation(context: ScopeContext) -> None:
    """Only Admin may assign or move an employee in the hierarchy."""

    if not context.can_write or context.scope is not Scope.ORG:
        raise ApiError(403, "forbidden", "Hierarchy changes are Admin-only.")
