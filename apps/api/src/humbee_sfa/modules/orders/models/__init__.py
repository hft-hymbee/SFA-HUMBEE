"""`orders` models — database-design.md §10. The highest-risk module: the database, not the
service layer, enforces the path/approval/money invariants. Read this file for the index; open a
specific module for column detail.

- `cart_draft.py`          `orders_cart_drafts` — the provisional basket before submit.
- `cart_line.py`           `orders_cart_lines` — child rows of a cart draft.
- `order.py`               `orders` — the order itself; carries the ~20 route/money CHECKs.
- `order_line.py`          `orders_lines` — per-SKU lines; per-line GST and money arithmetic.
- `po_reference.py`        `orders_po_references` — the PO an order draws down, one per order.
- `po_reference_line.py`   `orders_po_reference_lines` — per-SKU snapshot of that PO's lines.
- `submission_attempt.py`  `orders_submission_attempts` — append-only Humbee submission log.
- `status_event.py`        `orders_status_events` — append-only order timeline for S-ORD7.
- `approval_edit.py`       `orders_approval_edits` — audit trail of manager quantity edits.
"""

from __future__ import annotations

from humbee_sfa.modules.orders.models.approval_edit import ApprovalEdit
from humbee_sfa.modules.orders.models.cart_draft import CartDraft
from humbee_sfa.modules.orders.models.cart_line import CartLine
from humbee_sfa.modules.orders.models.order import Order
from humbee_sfa.modules.orders.models.order_line import OrderLine
from humbee_sfa.modules.orders.models.po_reference import PoReference
from humbee_sfa.modules.orders.models.po_reference_line import PoReferenceLine
from humbee_sfa.modules.orders.models.status_event import StatusEvent
from humbee_sfa.modules.orders.models.submission_attempt import SubmissionAttempt

__all__ = [
    "ApprovalEdit",
    "CartDraft",
    "CartLine",
    "Order",
    "OrderLine",
    "PoReference",
    "PoReferenceLine",
    "StatusEvent",
    "SubmissionAttempt",
]
