"""`approvals` models — database-design.md §6. Read this file for the index; open a specific
module for column detail.

- `request.py`   `Request` — `approvals_requests`, the single approval-request table serving beat
  create/edit, DP orders, leave and outlet verification.
- `decision.py`  `Decision` — `approvals_decisions`, append-only decision/audit trail per request.
"""

from __future__ import annotations

from humbee_sfa.modules.approvals.models.decision import Decision
from humbee_sfa.modules.approvals.models.request import Request

__all__ = [
    "Decision",
    "Request",
]
