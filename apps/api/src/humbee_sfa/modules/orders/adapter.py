"""`DpOrderAdapter` — orders' implementation of the approvals `ApprovalSubjectAdapter` contract
for `dp_order`.

The approval **subject_id is the cart id, not the order id**. `orders_approval_handle_chk`
requires `approval_request_id` to already be set the moment a `po_backed` order row is inserted —
one statement earlier than `approvals.service.create()` can hand one back. `OrderService.
submit_order` therefore calls `approvals.service.create()` *before* the order exists, using the
already-committed cart as the subject; `summary()` below renders from the cart, and every other
callback resolves the real order via `Order.cart_draft_id` (a real column, kept exactly for this).

One edge case: if the requester has no manager at all, `approvals.service.
create()` calls `on_approved` *inside itself*, before `OrderService.submit_order` has had a chance
to insert the order row. `on_approved` below no-ops when it cannot find an order yet;
`OrderService.submit_order` detects `request.status == AUTO_APPROVED` and finishes that case
itself.

`apply_edit` and the Humbee submission in `on_approved` need a wall-clock instant the
`ApprovalSubjectAdapter` Protocol does not thread an injected `Clock` through for — `SystemClock()`
is used narrowly there, and never for domain business-date derivation.

These callbacks run **inside** the engine's decision transaction on its own session:
they must never commit, roll back, or open a session of their own — the `LeaveAdapter`/
`BeatCreateAdapter` contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from humbee_sfa.core.clock import SystemClock
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.approvals.contracts import (
    Actor,
    ApprovalAdvisory,
    ApprovalStatus,
    DeepLink,
    EditableField,
    EditResult,
    NotificationSpec,
    SubjectDetailBlock,
    SubjectDetailBlocks,
    SubjectEditRejected,
    SubjectEvent,
    SubjectSummary,
    SubjectType,
)
from humbee_sfa.modules.approvals.models import Request
from humbee_sfa.modules.orders import repository
from humbee_sfa.modules.orders.models.approval_edit import ApprovalEdit
from humbee_sfa.modules.orders.models.order import Order
from humbee_sfa.modules.orders.service import (
    DP_SLA,
    _apportion,
    _basis_point_amount,
    append_status_event,
    submit_to_humbee,
)

STREAM = "orders"
AGGREGATE_ORDER = "order"

_OUTCOME_TITLES: dict[str, str] = {
    ApprovalStatus.APPROVED: "DP order approved",
    ApprovalStatus.APPROVED_WITH_EDITS: "DP order approved",
    ApprovalStatus.REJECTED: "DP order rejected",
    ApprovalStatus.WITHDRAWN: "DP order withdrawn",
}


def _order_for_cart(session: Session, *, tenant_id: str, cart_id: str) -> Order | None:
    return repository.get_order_by_cart(session, tenant_id=tenant_id, cart_draft_id=cart_id)


class DpOrderAdapter:
    subject_type = SubjectType.DP_ORDER

    # -- rendering -------------------------------------------------------------

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        cart = repository.get_cart(session, tenant_id=viewer.tenant_id, cart_id=subject_id)
        if cart is None:
            raise ApiError(404, "cart_not_found", "Cart was not found.")
        lines = repository.list_lines(session, cart_draft_id=cart.id)
        return SubjectSummary(
            title=f"DP order: {len(lines)} item(s)",
            subtitle=f"Outlet {cart.humbee_outlet_id} → {cart.humbee_manufacturer_id}",
            icon_key="ShoppingCartOutlined",
            requester_id=cart.employee_id,
            amount_paise=cart.gross_total_paise,
        )

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        order = _order_for_cart(session, tenant_id=viewer.tenant_id, cart_id=subject_id)
        if order is None:
            raise ApiError(404, "order_not_found", "Order was not found.")
        lines = repository.list_order_lines(session, order_id=order.id)
        subtotal_net_paise = (
            order.approved_subtotal_net_paise
            if order.approved_subtotal_net_paise is not None
            else order.subtotal_net_paise
        )
        scheme_discount_paise = min(order.scheme_discount_paise, subtotal_net_paise)
        gross_total_paise = (
            order.approved_gross_total_paise
            if order.approved_gross_total_paise is not None
            else order.gross_total_paise
        )
        gst_amount_paise = sum(
            (
                line.approved_line_gst_amount_paise
                if line.approved_line_gst_amount_paise is not None
                else line.line_gst_amount_paise
            )
            for line in lines
        )
        taxable_base_paise = gross_total_paise - gst_amount_paise

        priced_lines: list[dict[str, Any]] = []
        quantity_only_lines: list[dict[str, Any]] = []
        for line in lines:
            qty = line.approved_qty if line.approved_qty is not None else line.requested_qty
            line_net_paise = (
                line.approved_line_net_paise
                if line.approved_line_net_paise is not None
                else line.line_net_paise
            )
            line_gst_amount_paise = (
                line.approved_line_gst_amount_paise
                if line.approved_line_gst_amount_paise is not None
                else line.line_gst_amount_paise
            )
            line_payload = {
                "product_name": line.product_name_snapshot,
                "qty": qty,
                "unit_label": line.pack_size_snapshot or line.uom_snapshot,
                "unit_price_net_paise": line.unit_price_net_paise,
                "line_net_paise": line_net_paise,
                "line_gst_amount_paise": line_gst_amount_paise,
                "line_total_paise": line_net_paise + line_gst_amount_paise,
                **({"form_type": line.form_type} if line.form_type else {}),
            }
            if line.unit_price_net_paise is None:
                quantity_only_lines.append(line_payload)
            else:
                priced_lines.append(line_payload)

        return SubjectDetailBlocks(
            blocks=(
                SubjectDetailBlock(
                    kind="key_values",
                    label="Order",
                    payload={
                        "Outlet": order.outlet_name_snapshot,
                        "Manufacturer": order.manufacturer_name_snapshot,
                        "Source PO": order.humbee_po_id or "—",
                        "subtotal_net_paise": subtotal_net_paise,
                        "product_discount_paise": order.product_discount_paise,
                        "scheme_discount_paise": scheme_discount_paise,
                        "scheme_label": order.scheme_label_snapshot,
                        "taxable_base_paise": taxable_base_paise,
                        "gst_amount_paise": gst_amount_paise,
                        "gross_total_paise": gross_total_paise,
                    },
                ),
                SubjectDetailBlock(
                    kind="line_items",
                    label="Priced items",
                    payload={"lines": priced_lines},
                ),
                SubjectDetailBlock(
                    kind="line_items",
                    label="Quantity-only items",
                    payload={"lines": quantity_only_lines},
                ),
            )
        )

    # -- editing: qty-only (`orders_approval_edits.field = 'qty'`) ----

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        # No tenant/viewer on this Protocol method; `cart_draft_id` is a globally-unique ULID, so
        # the tenant-agnostic lookup is safe (same reasoning as every other ULID PK in this system).
        order = repository.get_order_by_cart_global(session, cart_draft_id=subject_id)
        if order is None or order.status != "pending_approval":
            return []  # no fields hides the Edit button
        lines = repository.list_order_lines(session, order_id=order.id)
        return [
            EditableField(
                key=line.id,
                label=line.product_name_snapshot,
                kind="integer_stepper",
                current_value=(
                    line.approved_qty if line.approved_qty is not None else line.requested_qty
                ),
                min_value=0,
                max_value=line.requested_qty,
            )
            for line in lines
        ]

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        order = _order_for_cart(session, tenant_id=actor.tenant_id, cart_id=subject_id)
        if order is None or order.status != "pending_approval":
            raise SubjectEditRejected("This order is no longer pending approval.")
        lines_by_id = {
            line.id: line for line in repository.list_order_lines(session, order_id=order.id)
        }
        now = SystemClock().now_utc()  # see module docstring: no clock threaded to this Protocol
        patch_applied: dict[str, Any] = {}

        for line_id, raw_qty in patch.items():
            line = lines_by_id.get(line_id)
            if line is None:
                raise SubjectEditRejected(f"Unknown order line {line_id!r}.", field_key=line_id)
            try:
                new_qty = int(raw_qty)
            except (TypeError, ValueError) as exc:
                raise SubjectEditRejected(
                    "Quantity must be an integer.", field_key=line_id
                ) from exc
            if not (0 <= new_qty <= line.requested_qty):
                raise SubjectEditRejected(
                    f"Quantity must be between 0 and {line.requested_qty}.", field_key=line_id
                )
            before = line.approved_qty if line.approved_qty is not None else line.requested_qty
            if new_qty == before:
                continue
            line.approved_qty = new_qty
            line.approved_line_net_paise = (line.unit_price_net_paise or 0) * new_qty
            session.add(
                ApprovalEdit(
                    tenant_id=order.tenant_id,
                    order_id=order.id,
                    order_line_id=line.id,
                    # No decision row exists yet — the engine appends it right after this call
                    # returns. `approval_request_id` is the closest real, already-persisted
                    # correlator; `orders_approval_edits.approval_decision_id` is logical-only
                    # (no FK/CHECK), matching its own docstring.
                    approval_decision_id=order.approval_request_id or order.id,
                    product_name_snapshot=line.product_name_snapshot,
                    field="qty",
                    before_value=before,
                    after_value=new_qty,
                    edited_by_employee_id=actor.employee_id,
                    edited_at=now,
                    created_by_employee_id=actor.employee_id,
                )
            )
            patch_applied[line_id] = {"before": before, "after": new_qty}

        lines = list(lines_by_id.values())
        approved_nets = [
            (line.unit_price_net_paise or 0)
            * (line.approved_qty if line.approved_qty is not None else line.requested_qty)
            for line in lines
        ]
        approved_subtotal_net_paise = sum(approved_nets)
        # Re-apportion the ORIGINAL scheme and product discounts over the (possibly reduced)
        # approved amounts — same largest-remainder formula built for the cart. Prices are never
        # re-fetched at approval time.
        discount_paise = min(order.scheme_discount_paise, approved_subtotal_net_paise)
        product_discount_paise = min(
            order.product_discount_paise, approved_subtotal_net_paise - discount_paise
        )
        discount_shares = _apportion(discount_paise, approved_nets)
        product_discount_shares = _apportion(product_discount_paise, approved_nets)
        for line, net, discount_share, product_discount_share in zip(
            lines, approved_nets, discount_shares, product_discount_shares, strict=True
        ):
            taxable = net - discount_share - product_discount_share
            line.approved_line_gst_amount_paise = _basis_point_amount(taxable, line.gst_rate_bp)
        order.approved_subtotal_net_paise = approved_subtotal_net_paise
        approved_gst_paise = sum(line.approved_line_gst_amount_paise or 0 for line in lines)
        order.approved_gross_total_paise = (
            approved_subtotal_net_paise - discount_paise - product_discount_paise + approved_gst_paise
        )
        session.flush()

        item_count = sum(
            1
            for line in lines
            if (line.approved_qty if line.approved_qty is not None else line.requested_qty) > 0
        )
        return EditResult(
            summary=SubjectSummary(
                title=f"DP order: {item_count} item(s)",
                subtitle=order.outlet_name_snapshot,
                icon_key="ShoppingCartOutlined",
                requester_id=order.employee_id,
                amount_paise=order.approved_gross_total_paise,
            ),
            subject_version=2,  # orders support exactly one edit-and-approve shot
            patch_applied=patch_applied,
        )

    # -- outcome callbacks (run inside the approvals engine's decision transaction) --------------

    def on_approved(
        self, session: Session, *, request: Request, decided_at: datetime
    ) -> list[SubjectEvent]:
        order = _order_for_cart(session, tenant_id=request.tenant_id, cart_id=request.subject_id)
        if order is None:
            return []  # auto-approved-at-creation edge case; `submit_order` finishes it itself
        order.status = "approved_with_edits" if request.edit_applied else "approved"
        order.approved_at = decided_at
        order.dp_sla_deadline_at = decided_at + DP_SLA
        append_status_event(
            session,
            order,
            kind="approved_with_edits" if request.edit_applied else "approved",
            title="Approved with edits" if request.edit_applied else "Approved",
            detail="Line quantities were reduced" if request.edit_applied else "No edits",
            occurred_at=decided_at,
            timeline_state="edited" if request.edit_applied else "done",
            actor_employee_id=request.decided_by_id,
        )
        # Registers with Humbee synchronously, inside this decision transaction. Never commits or
        # rolls back here (see module docstring) — the engine commits the whole decision,
        # including whatever this call staged, once every subject callback has returned.
        submit_to_humbee(
            session,
            order=order,
            clock=SystemClock(),
            settings=get_settings(),
            trigger="outbox_auto",
        )
        return [
            SubjectEvent(
                stream=STREAM,
                event_type="dp_order_approved",
                aggregate_type=AGGREGATE_ORDER,
                aggregate_id=order.id,
                payload={"order_id": order.id, "status": order.status},
            )
        ]

    def on_rejected(
        self, session: Session, *, request: Request, reason: str, decided_at: datetime
    ) -> list[SubjectEvent]:
        order = _order_for_cart(session, tenant_id=request.tenant_id, cart_id=request.subject_id)
        if order is None:
            return []
        order.status = "rejected"
        order.sub_status_reason = reason or None
        append_status_event(
            session,
            order,
            kind="rejected",
            title=f"Rejected by {order.approver_name_snapshot or 'your manager'}",
            detail=reason or None,
            occurred_at=decided_at,
            timeline_state="rejected",
            actor_employee_id=request.decided_by_id,
        )
        # No outbox row, ever — rejection triggers no downstream registration.
        return [
            SubjectEvent(
                stream=STREAM,
                event_type="dp_order_rejected",
                aggregate_type=AGGREGATE_ORDER,
                aggregate_id=order.id,
                payload={"order_id": order.id},
            )
        ]

    def on_withdrawn(
        self, session: Session, *, request: Request, decided_at: datetime
    ) -> list[SubjectEvent]:
        order = _order_for_cart(session, tenant_id=request.tenant_id, cart_id=request.subject_id)
        if order is None:
            return []
        order.status = "cancelled"
        order.cancelled_at = decided_at
        append_status_event(
            session,
            order,
            kind="cancelled",
            title="Cancelled",
            detail=None,
            occurred_at=decided_at,
            timeline_state="rejected",
        )
        return [
            SubjectEvent(
                stream=STREAM,
                event_type="dp_order_withdrawn",
                aggregate_type=AGGREGATE_ORDER,
                aggregate_id=order.id,
                payload={"order_id": order.id},
            )
        ]

    # -- advisory + notification -------------------------------------------------

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]:
        return []

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec:
        return NotificationSpec(
            kind=str(outcome),
            title=_OUTCOME_TITLES.get(str(outcome), request.title),
            subtitle=request.title,
            recipient_id=request.requester_id,
            dedupe_key=f"approval:{request.id}:{outcome}",
        )

    def deep_link(self, request: Request, viewer: Actor) -> DeepLink:
        # No `session` on this Protocol method, so the real order id (which differs from
        # `subject_id` — see module docstring) cannot be resolved here; the approval request
        # screen is reachable for both the requester and the approver either way.
        return DeepLink(target_type="approval_request", target_id=request.id)


__all__ = ["DpOrderAdapter"]
