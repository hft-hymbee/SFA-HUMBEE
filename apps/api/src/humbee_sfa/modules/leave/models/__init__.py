"""`leave` models. Read this file for the index; open a specific module for column detail.

- `leave_request.py`   `LeaveRequest` — `leave_requests`, the leave-application record, carries the
  `leave_no_overlap_excl` GIST exclusion constraint that is the `is_on_leave()` oracle.
- `leave_balance.py`   `LeaveBalance` — `leave_balances`, per-employee/type/year entitlement ledger.

`leave_days` is a database VIEW, not a table — there is no ORM model for it here. It is
read-only, defined by raw SQL in a migration, and out of scope for module models.
"""

from __future__ import annotations

from humbee_sfa.modules.leave.models.leave_balance import LeaveBalance
from humbee_sfa.modules.leave.models.leave_request import LeaveRequest

__all__ = [
    "LeaveBalance",
    "LeaveRequest",
]
