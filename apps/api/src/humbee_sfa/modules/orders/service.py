"""Orders/cart business logic — Story 4.1 (M10 §3.3, §5.1-5.4, §7 R-ORD-03/07/16/17/22/26/27),
reshaped by epic 07 Stories 7.4-7.6 around the verified Humbee contract
(`docs/features/03-humbee-integration-contract.md` §8).

Transaction ownership lives here, mirroring `routes.service`. A cart is `SELF`-only end to end
(M10 §9: "Add products / edit cart — ✅ own cart" only, no manager/admin path exists for a cart),
so ownership is a direct `employee_id` equality check rather than the full `ScopeResolver` —
there is no OWN_TREE/ORG cart read to resolve against. "A valid visit" is established by calling
`routes.service.RouteService.get_day` — the module's own public read — never by querying
`routes_visits` directly (routes/attendance/beats are read-only dependencies here).

Order routing (PO-backed vs direct, approval-required or not) is decided entirely by the seller
chosen for the outlet+brand (`integration/humbee/seller.py`) — there is no outlet classification
or tier anywhere in this file any more; the verified build does not expose one (§8).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from humbee_sfa.core.business_date import to_business_date
from humbee_sfa.core.clock import Clock, SystemClock
from humbee_sfa.core.conventions import generate_ulid
from humbee_sfa.core.db import transaction
from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.commerce import (
    CommerceUnavailable,
    HumbeeCommerceProvider,
    OrderRegistrationFailed,
    ProductRecord,
    PurchaseOrderRecord,
    RegisterOrderLine,
    SchemeUnavailable,
    ServiceableGeographyUnavailable,
    ShipToOption,
)
from humbee_sfa.integration.humbee.geography import (
    GeographyMasterUnavailable,
    HumbeeGeographyMasterProvider,
)
from humbee_sfa.integration.humbee.outlet import HumbeeOutletMasterProvider
from humbee_sfa.integration.humbee.seller import (
    BrandSellers,
    EsiRecord,
    HumbeeSellerLinkageProvider,
    SellerLinkageUnavailable,
    SellerRecord,
)
from humbee_sfa.modules.approvals import service as approvals_service
from humbee_sfa.modules.approvals.contracts import ApprovalStatus, SubjectType
from humbee_sfa.modules.orders import events, repository, schemas
from humbee_sfa.modules.orders.models.cart_draft import CartDraft
from humbee_sfa.modules.orders.models.cart_line import CartLine
from humbee_sfa.modules.orders.models.order import Order
from humbee_sfa.modules.orders.models.order_line import OrderLine
from humbee_sfa.modules.orders.models.po_reference import PoReference
from humbee_sfa.modules.orders.models.status_event import StatusEvent
from humbee_sfa.modules.orders.models.submission_attempt import SubmissionAttempt
from humbee_sfa.modules.org import service as org_service
from humbee_sfa.modules.org.scope import OrgResource, ScopeResolver
from humbee_sfa.modules.outlets.service import OutletReadService
from humbee_sfa.modules.routes.service import RouteService
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.idempotency import IdempotencyService

logger = structlog.get_logger("humbee_sfa.orders")

CART_TTL_HOURS = 24  # R-ORD-21 default; M10 §3.3
DP_SLA = timedelta(hours=1)  # M10 §3a "1-hour DP creation SLA"; runtime-config default
MANUAL_RETRY_COOLDOWN = timedelta(minutes=5)  # M10 §11.3 "default 1 per 5 min per order"
_ORDERED_STATUSES = (
    "submitted",
    "pending_approval",
    "approved",
    "approved_with_edits",
    "dp_creation_pending",
    "dp_created",
)


def _previous_month_start(month_start: date) -> date:
    if month_start.month == 1:
        return month_start.replace(year=month_start.year - 1, month=12)
    return month_start.replace(month=month_start.month - 1)

# M10 §11.2: classes a manual retry must never be offered for. Terminal classes need a new order,
# not a resubmission; `timeout` (which also covers Humbee's own `999` unhandled-exception code,
# integration/humbee/commerce.py) means whether the write landed at Humbee is genuinely
# unknown — a resubmission here is exactly the "risks a duplicate order" case M10 §11.2 warns
# against, so it stays operator-resolved rather than auto- or user-blind-retried.
_MANUAL_RETRY_BLOCKED_CLASSES = frozenset(
    {
        "po_closed", "po_consumed", "po_expired", "po_value_exceeded", "credit_rejected",
        "validation_rejected", "outlet_inactive", "timeout", "duplicate_reference",
    }
)
_FAILURE_REASON_BY_CLASS = {
    "timeout": (
        "Submission timed out; whether it reached Humbee is unknown. An operator must "
        "reconcile before any retry."
    ),
    "outlet_inactive": "This outlet is inactive in Humbee, so the order cannot be registered.",
}


def _fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _round_half_up(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_UP))


def _basis_point_amount(amount_paise: int, rate_bp: int) -> int:
    if rate_bp <= 0:
        return 0
    return _round_half_up(Decimal(amount_paise) * Decimal(rate_bp) / Decimal(10000))


def _line_product_discount_paise(unit_price_net_paise: int | None, discount_rate_bp: int, qty: int) -> int:
    """discount_rate_bp is applied to unit_price_net_paise, catalog's GST-exclusive base — the
    same basis scheme_discount_paise applies against subtotal_net_paise."""

    if unit_price_net_paise is None:
        return 0
    return _basis_point_amount(unit_price_net_paise, discount_rate_bp) * qty


def _product_discount_paise(
    lines: list[CartLine],
    products: dict[str, ProductRecord],
) -> int:
    total = 0
    for line in lines:
        product = products.get(line.humbee_product_id)
        if product is None:
            continue
        total += _line_product_discount_paise(line.unit_price_net_paise, product.discount_rate_bp, line.qty)
    return total


def _apportion(total: int, weights: list[int]) -> list[int]:
    """Split `total` across `weights` so the parts sum to exactly `total` (largest-remainder)."""

    weight_sum = sum(weights)
    if total <= 0 or weight_sum <= 0:
        return [0] * len(weights)
    shares = [(total * w) // weight_sum for w in weights]
    remainder = total - sum(shares)
    order = sorted(range(len(weights)), key=lambda i: (total * weights[i]) % weight_sum, reverse=True)
    for i in order[:remainder]:
        shares[i] += 1
    return shares


def _product_district_id(
    outlets: OutletReadService, *, tenant_id: str, cart: CartDraft
) -> str | None:
    if cart.shipping_address_district_id:
        return cart.shipping_address_district_id
    projected = outlets.get_projected_outlets(
        tenant_id=tenant_id, outlet_ids=[cart.humbee_outlet_id]
    )
    return projected[0].record.district_external_id if projected else None


def _order_path_for(seller: SellerRecord) -> schemas.OrderPath:
    return "po_backed" if seller.requires_purchase_order else "direct"


def _banner_for(seller: SellerRecord, order_path: schemas.OrderPath) -> str:
    if order_path == "po_backed":
        return (
            f"{seller.name} — this order draws down an open purchase order and needs manager "
            "approval; it is created within one hour of approval."
        )
    if seller.manager_approval_required:
        return f"{seller.name} — this order needs manager approval before it is sent."
    return f"{seller.name} — this order is created directly, no manager approval needed."


def _esi_ids_for(seller: SellerRecord) -> tuple[str | None, str | None]:
    """Picks the outlet's own ESI (`buyer_esi_id`) and, on a secondary order, the seller's own ESI
    (`seller_esi_id`) from `SellerRecord`. Both are lists because a firm can hold more than one
    registration (§9.1) — SFA has no picker for this yet, so the first is used and a warning is
    logged when there was a real choice to make, rather than silently guessing wrong."""

    def _first(records: tuple[EsiRecord, ...], label: str) -> str | None:
        if not records:
            return None
        if len(records) > 1:
            logger.warning("humbee_esi_ambiguous", label=label, count=len(records))
        return records[0].esi_id

    buyer_esi_id = _first(seller.outlet_esi_records, "outlet_esi_records")
    seller_esi_id = _first(seller.seller_esi_records, "seller_esi_records")
    return buyer_esi_id, seller_esi_id


def _shipping_override(
    line1: str | None, line2: str | None, state_id: str | None, district_id: str | None,
    pincode: str | None,
) -> schemas.ShippingAddressOverride | None:
    if line1 is None or state_id is None or district_id is None or pincode is None:
        return None
    return schemas.ShippingAddressOverride(
        line1=line1, line2=line2, state_id=state_id, district_id=district_id, pincode=pincode,
    )


def _po_cap(po: PurchaseOrderRecord) -> tuple[int | None, str | None]:
    """`min(max_dp_quantity, available_quantity)`, naming whichever bound it."""

    candidates = [
        (po.max_dp_quantity, "max_dp_quantity"), (po.available_quantity, "available_quantity"),
    ]
    present = [(value, label) for value, label in candidates if value is not None]
    if not present:
        return None, None
    value, label = min(present, key=lambda item: item[0])
    return value, label


def _po_line_balance(po: PurchaseOrderRecord, product_id: str) -> int | None:
    """The remaining orderable quantity for one SKU on this PO, or `None` when the PO carries no
    line for it (nothing to cap against — P-2 `lines[].balance_qty`)."""

    line = next((line for line in po.lines if line.product_id == product_id), None)
    return line.balance_qty if line is not None else None


class CartService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        outlet_port: HumbeeOutletMasterProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._outlet_port = outlet_port
        self._idempotency = IdempotencyService(session)

    # -- shared helpers -----------------------------------------------------

    def _po_record_for_cart(
        self, claims: AccessTokenClaims, cart: CartDraft, commerce: HumbeeCommerceProvider,
    ) -> PurchaseOrderRecord | None:
        if cart.order_path != "po_backed" or not cart.humbee_po_id:
            return None
        pos = commerce.list_open_purchase_orders(
            tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
            manufacturer_id=cart.humbee_manufacturer_id, outlet_esi_id=cart.humbee_buyer_esi_id,
        )
        return next((p for p in pos if p.external_id == cart.humbee_po_id), None)

    def _po_cap_for_cart(
        self, claims: AccessTokenClaims, cart: CartDraft, commerce: HumbeeCommerceProvider,
    ) -> tuple[int | None, str | None]:
        po = self._po_record_for_cart(claims, cart, commerce)
        return _po_cap(po) if po is not None else (None, None)

    def _enforce_po_cap(
        self, claims: AccessTokenClaims, cart: CartDraft,
        lines: list[schemas.UpsertLineBody], commerce: HumbeeCommerceProvider,
    ) -> None:
        po = self._po_record_for_cart(claims, cart, commerce)
        if po is None:
            return
        for line in lines:
            line_balance = _po_line_balance(po, line.product_id)
            if line_balance is not None and line.qty > line_balance:
                raise ApiError(
                    422, "po_line_quantity_exceeded",
                    f"This product needs {line.qty} units, more than the {line_balance} still "
                    "available on the purchase order.",
                )
        po_cap_qty, _ = _po_cap(po)
        if po_cap_qty is None:
            return
        updated_ids = {line.product_id for line in lines}
        baseline_qty = sum(
            existing_line.qty
            for existing_line in repository.list_lines(self._session, cart_draft_id=cart.id)
            if existing_line.humbee_product_id not in updated_ids
        )
        prospective_qty = baseline_qty + sum(line.qty for line in lines)
        if prospective_qty > po_cap_qty:
            raise ApiError(
                422, "po_quantity_exceeded",
                f"This cart needs {prospective_qty} units, more than the {po_cap_qty} still "
                "available on the purchase order.",
            )

    def _outlets(self) -> OutletReadService:
        return OutletReadService(
            self._session,
            settings=self._settings,
            clock=self._clock,
            outlet_port=self._outlet_port,
        )

    def _commerce(self) -> HumbeeCommerceProvider:
        try:
            return HumbeeCommerceProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "Commerce data is unavailable right now."
            ) from exc

    def _delivers_to_district(
        self, *, tenant_id: str, manufacturer_id: str, district_id: str | None
    ) -> bool:
        """Serviceability for a district we hold only by id.

        C-15 is bounded by state, so the district's state is resolved through the geography master
        first — two upstream calls where a national listing used to be one. A district we cannot
        place, or one we were never given, is unanswerable rather than unserviceable: it raises, so
        the caller reports "could not be confirmed" instead of telling a shopkeeper the
        manufacturer does not deliver to them.
        """

        if not district_id:
            raise ServiceableGeographyUnavailable("no district on the delivery address")
        try:
            state_id = HumbeeGeographyMasterProvider(self._settings).fetch_state_of_district(
                tenant_id=tenant_id, district_id=district_id
            )
        except GeographyMasterUnavailable as exc:
            raise ServiceableGeographyUnavailable(str(exc)) from exc
        if state_id is None:
            raise ServiceableGeographyUnavailable(f"district {district_id} is not in the master")
        return self._commerce().is_district_serviceable(
            tenant_id=tenant_id,
            manufacturer_id=manufacturer_id,
            state_id=state_id,
            district_id=district_id,
        )

    def _sellers(self) -> HumbeeSellerLinkageProvider:
        try:
            return HumbeeSellerLinkageProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(503, "upstream_unavailable", "Seller data is unavailable right now.") from exc

    def _brand_sellers(
        self, *, tenant_id: str, outlet_id: str, manufacturer_id: str
    ) -> BrandSellers | None:
        try:
            snapshot = self._sellers().get_outlet_sellers(tenant_id=tenant_id, outlet_id=outlet_id)
        except SellerLinkageUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Seller data is unavailable right now."
            ) from exc
        return next((b for b in snapshot.brands if b.brand_id == manufacturer_id), None)

    def _resolve_seller(
        self, *, tenant_id: str, outlet_id: str, manufacturer_id: str, seller_id: str | None
    ) -> SellerRecord:
        """Resolves the one seller a cart/order is created against. Zero linked sellers and an
        unresolved multi-seller ambiguity are both real, distinct 422s a client renders a
        recovery/selection screen from — never guessed past."""

        brand = self._brand_sellers(
            tenant_id=tenant_id, outlet_id=outlet_id, manufacturer_id=manufacturer_id
        )
        active = [s for s in (brand.sellers if brand else ()) if s.is_active]
        if not active:
            raise ApiError(422, "no_sellers_linked", "This outlet has no sellers linked for this brand.")
        if seller_id is not None:
            seller = next((s for s in active if s.external_id == seller_id), None)
            if seller is None:
                raise ApiError(
                    422, "seller_not_linked", "This seller is not linked to the outlet for this brand."
                )
            return seller
        if len(active) > 1:
            raise ApiError(422, "seller_selection_required", "Select a seller before continuing.")
        return active[0]

    def _resolve_seller_by_seller_esi(
        self, *, tenant_id: str, outlet_id: str, manufacturer_id: str, seller_esi_id: str
    ) -> SellerRecord | None:
        brand = self._brand_sellers(
            tenant_id=tenant_id, outlet_id=outlet_id, manufacturer_id=manufacturer_id
        )
        active = [s for s in (brand.sellers if brand else ()) if s.is_active]
        matches = [
            seller
            for seller in active
            if any(esi.esi_id == seller_esi_id for esi in seller.seller_esi_records)
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    def _resolve_active_visit_outlet(self, claims: AccessTokenClaims, visit_id: str) -> str:
        """R-ORD-53: an active visit, resolved only through `routes.service`'s public surface.

        Uses `get_active_visit_outlet` rather than `get_day` so this works for an unplanned
        visit too — an unplanned visit has a `RouteVisit` row but no `RoutePlan` (M08 transition #2).
        """

        return RouteService(
            self._session, settings=self._settings, clock=self._clock
        ).get_active_visit_outlet(claims=claims, visit_id=visit_id)

    def _own_cart(self, claims: AccessTokenClaims, cart_id: str) -> CartDraft:
        cart = repository.get_cart(self._session, tenant_id=claims.tenant_id, cart_id=cart_id)
        if cart is None or cart.employee_id != claims.employee_id:
            raise ApiError(404, "cart_not_found", "Cart was not found.")
        return cart

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        existing = self._idempotency.get(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _fingerprint(raw_body)):
            raise ApiError(
                409, "idempotency_conflict", "Idempotency key was already used with a different payload."
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, status_code: int,
        payload: dict[str, Any], tenant_id: str, actor_employee_id: str,
    ) -> None:
        self._idempotency.save(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key,
            request_fingerprint=_fingerprint(raw_body),
            response_fingerprint=_fingerprint(json.dumps(payload, sort_keys=True, default=str).encode()),
            status_code=status_code, response_payload=payload, actor_employee_id=actor_employee_id,
        )

    def _products_by_id(
        self, commerce: HumbeeCommerceProvider, *, tenant_id: str, outlet_id: str, manufacturer_id: str,
        outlet_esi_id: str | None, seller_esi_id: str | None, district_id: str | None,
    ) -> dict[str, ProductRecord]:
        try:
            products = commerce.list_products(
                tenant_id=tenant_id, outlet_id=outlet_id, manufacturer_id=manufacturer_id,
                outlet_esi_id=outlet_esi_id, seller_esi_id=seller_esi_id, district_id=district_id,
                po_id=None, category=None, query=None,
            )
        except CommerceUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Commerce data is unavailable right now."
            ) from exc
        return {p.external_id: p for p in products}

    # -- cart lifecycle -------------------------------------------------------

    def create_or_get_cart(
        self, *, claims: AccessTokenClaims, body: schemas.CreateCartBody
    ) -> tuple[int, dict[str, Any]]:
        """S-ORD1 entry (M10 §5.1 step 1). Resumes the open cart for the tuple if one exists.

        When the selected seller changes for the same `(visit, outlet, manufacturer)` tuple, the
        old open cart cannot be reused: seller-bound ESI, PO and pricing context become invalid.
        The old draft is moved to `abandoned` and a new open cart is created for the selected
        seller.
        """

        outlet_ref = self._resolve_active_visit_outlet(claims, body.visit_id)
        if outlet_ref != body.outlet_id:
            raise ApiError(422, "outlet_mismatch", "The outlet does not match the active visit.")

        seller = self._resolve_seller(
            tenant_id=claims.tenant_id, outlet_id=body.outlet_id,
            manufacturer_id=body.manufacturer_id, seller_id=body.seller_id,
        )

        existing = repository.get_open_cart(
            self._session, tenant_id=claims.tenant_id, employee_id=claims.employee_id,
            visit_id=body.visit_id, outlet_id=body.outlet_id, manufacturer_id=body.manufacturer_id,
        )
        if existing is not None:
            if existing.humbee_seller_id == seller.external_id:
                return 200, self._cart_payload(claims, existing, revalidate=False)
            with transaction(self._session):
                existing.status = "abandoned"

        order_path = _order_path_for(seller)
        buyer_esi_id, seller_esi_id = _esi_ids_for(seller)

        now = self._clock.now_utc()
        cart = CartDraft(
            tenant_id=claims.tenant_id, employee_id=claims.employee_id, visit_id=body.visit_id,
            humbee_outlet_id=body.outlet_id, order_path=order_path,
            seller_type_snapshot=seller.seller_type, humbee_manufacturer_id=body.manufacturer_id,
            humbee_seller_id=seller.external_id,
            humbee_buyer_esi_id=buyer_esi_id, humbee_seller_esi_id=seller_esi_id,
            ship_to_type="self" if order_path == "po_backed" else None,
            status="open", expires_at=now + timedelta(hours=CART_TTL_HOURS),
            created_by_employee_id=claims.employee_id,
        )
        try:
            with transaction(self._session):
                self._session.add(cart)
        except IntegrityError:
            # One open cart per (visit, outlet, manufacturer): a concurrent opener already won, so
            # this returns theirs rather than failing. Mapped outside the `with`, which has
            # already rolled back, so the lookup below runs in a clean transaction.
            existing = repository.get_open_cart(
                self._session, tenant_id=claims.tenant_id, employee_id=claims.employee_id,
                visit_id=body.visit_id, outlet_id=body.outlet_id,
                manufacturer_id=body.manufacturer_id,
            )
            if existing is None:
                raise
            return 200, self._cart_payload(claims, existing, revalidate=False)
        return 201, self._cart_payload(claims, cart, revalidate=False)

    def get_cart(self, *, claims: AccessTokenClaims, cart_id: str) -> dict[str, Any]:
        """S-ORD3 (M10 §5.4): re-prices and re-evaluates the scheme on every read (R-ORD-07)."""

        cart = self._own_cart(claims, cart_id)
        with transaction(self._session):
            payload = self._cart_payload(claims, cart, revalidate=True)
        return payload

    def patch_cart(
        self, *, claims: AccessTokenClaims, cart_id: str, body: schemas.PatchCartBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Sets `source_po_id` / ship-to / address override (M10 §5.1-5.2)."""

        cart = self._own_cart(claims, cart_id)
        endpoint = f"PATCH /carts/{cart_id}"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=claims.tenant_id,
        )
        if replay is not None:
            return replay
        if cart.status != "open":
            raise ApiError(409, "cart_not_open", "This cart is no longer open.")
        if cart.visit_id is not None:
            self._resolve_active_visit_outlet(claims, cart.visit_id)

        if body.outlet_esi_id is not None or body.seller_esi_id is not None:
            seller = self._resolve_seller(
                tenant_id=claims.tenant_id,
                outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                seller_id=cart.humbee_seller_id,
            )
            seller_rebound = False
            if body.seller_esi_id is not None:
                if seller.seller_type == "MANUFACTURER":
                    if body.seller_esi_id:
                        raise ApiError(
                            422,
                            "seller_esi_not_applicable",
                            "Manufacturer sellers do not use a seller ESI.",
                        )
                    cart.humbee_seller_esi_id = None
                else:
                    if not body.seller_esi_id:
                        raise ApiError(
                            422,
                            "seller_esi_required",
                            "A seller delivery-location ESI is required for this seller.",
                        )
                    if not any(esi.esi_id == body.seller_esi_id for esi in seller.seller_esi_records):
                        rebound = self._resolve_seller_by_seller_esi(
                            tenant_id=claims.tenant_id,
                            outlet_id=cart.humbee_outlet_id,
                            manufacturer_id=cart.humbee_manufacturer_id,
                            seller_esi_id=body.seller_esi_id,
                        )
                        if rebound is not None and rebound.external_id != seller.external_id:
                            # A cart resumed from an older flow can be bound to a stale seller.
                            # When one active seller uniquely owns this seller ESI, rebind the
                            # cart to keep ESI patch deterministic.
                            seller = rebound
                            seller_rebound = True
                            cart.humbee_seller_id = rebound.external_id
                            cart.seller_type_snapshot = rebound.seller_type
                            cart.order_path = _order_path_for(rebound)
                            cart.humbee_po_id = None
                            cart.ship_to_type = "self" if cart.order_path == "po_backed" else None
                            cart.ship_to_humbee_outlet_id = None
                            cart.ship_to_humbee_esi_id = None
                            cart.shipping_address_line1 = None
                            cart.shipping_address_line2 = None
                            cart.shipping_address_state_id = None
                            cart.shipping_address_district_id = None
                            cart.shipping_address_pincode = None
                        else:
                            raise ApiError(
                                422,
                                "seller_esi_not_mapped",
                                "This seller delivery-location ESI is not linked to the selected seller.",
                            )
                    cart.humbee_seller_esi_id = body.seller_esi_id
            if body.outlet_esi_id is not None:
                if not any(esi.esi_id == body.outlet_esi_id for esi in seller.outlet_esi_records):
                    raise ApiError(
                        422,
                        "buyer_esi_not_mapped",
                        "This outlet shipping ESI is not linked to the selected seller.",
                    )
                cart.humbee_buyer_esi_id = body.outlet_esi_id
            elif seller_rebound:
                if not cart.humbee_buyer_esi_id or not any(
                    esi.esi_id == cart.humbee_buyer_esi_id for esi in seller.outlet_esi_records
                ):
                    buyer_esi_id, _ = _esi_ids_for(seller)
                    cart.humbee_buyer_esi_id = buyer_esi_id

        commerce = self._commerce()
        if body.source_po_id is not None:
            if cart.order_path != "po_backed":
                raise ApiError(
                    422, "po_not_applicable", "Only purchase-order-backed orders reference a PO."
                )
            pos = commerce.list_open_purchase_orders(
                tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                outlet_esi_id=cart.humbee_buyer_esi_id,
            )
            if not any(po.external_id == body.source_po_id for po in pos):
                raise ApiError(422, "po_not_open", "This purchase order is not open.")  # R-ORD-09
            cart.humbee_po_id = body.source_po_id

        if body.ship_to_type is not None:
            if body.ship_to_type == "dealer":
                if not body.ship_to_outlet_id or not body.ship_to_esi_id:
                    raise ApiError(
                        422, "ship_to_outlet_required",
                        "A ship-to outlet and its ESI registration are required.",
                    )
                if not cart.humbee_buyer_esi_id:
                    raise ApiError(
                        422, "buyer_esi_unresolved",
                        "This outlet's ESI registration could not be resolved.",
                    )
                options = commerce.list_ship_to_options(
                    tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                    buyer_esi_id=cart.humbee_buyer_esi_id,
                )
                # A party can hold more than one ESI-backed operational address (a separate
                # internal shop or registration each), so both ids together — never the party
                # alone — identify which one was picked (R-ORD-15).
                matches = [
                    o for o in options
                    if o.party_id == body.ship_to_outlet_id and o.esi_id == body.ship_to_esi_id
                ]
                if not matches:
                    raise ApiError(
                        422, "ship_to_not_mapped", "This ship-to outlet is not a valid option.",
                    )
                selected = matches[0]
                try:
                    serviceable = self._delivers_to_district(
                        tenant_id=claims.tenant_id,
                        manufacturer_id=cart.humbee_manufacturer_id,
                        district_id=selected.district_id,
                    )
                except ServiceableGeographyUnavailable as exc:
                    raise ApiError(
                        422, "delivery_unconfirmed",
                        "Delivery availability could not be confirmed right now.",
                    ) from exc
                if not serviceable:
                    raise ApiError(
                        422, "ship_to_not_serviceable",
                        "This manufacturer does not deliver to this address.",
                    )
                cart.ship_to_type = "dealer"
                cart.ship_to_humbee_outlet_id = selected.party_id
                cart.ship_to_humbee_esi_id = selected.esi_id
            else:
                cart.ship_to_type = "self"
                cart.ship_to_humbee_esi_id = None
                cart.ship_to_humbee_outlet_id = None

        if body.shipping_address_override is not None:
            override = body.shipping_address_override
            try:
                # The only check that needs no geography lookup — the override carries its state.
                serviceable = commerce.is_district_serviceable(
                    tenant_id=claims.tenant_id,
                    manufacturer_id=cart.humbee_manufacturer_id,
                    state_id=override.state_id,
                    district_id=override.district_id,
                )
            except ServiceableGeographyUnavailable as exc:
                raise ApiError(
                    422, "delivery_unconfirmed",
                    "Delivery availability could not be confirmed right now.",
                ) from exc
            if not serviceable:
                raise ApiError(
                    422, "address_not_serviceable",
                    "This manufacturer does not deliver to the selected district.",
                )
            cart.shipping_address_line1 = override.line1
            cart.shipping_address_line2 = override.line2
            cart.shipping_address_state_id = override.state_id
            cart.shipping_address_district_id = override.district_id
            cart.shipping_address_pincode = override.pincode

        with transaction(self._session):
            self._session.flush()
            payload = self._cart_payload(claims, cart, revalidate=False)
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=claims.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload

    def upsert_line(
        self, *, claims: AccessTokenClaims, cart_id: str, body: schemas.UpsertLinesBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """S-ORD2/S-ORD3 line mutations (R-ORD-16/17/18/20). `qty = 0` removes the line."""

        cart = self._own_cart(claims, cart_id)
        endpoint = f"PUT /carts/{cart_id}/lines"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=claims.tenant_id,
        )
        if replay is not None:
            return replay
        if cart.status != "open":
            raise ApiError(409, "cart_not_open", "This cart is no longer open.")
        if cart.visit_id is not None:
            self._resolve_active_visit_outlet(claims, cart.visit_id)

        lines = body.lines
        sellable_products: dict[str, ProductRecord] = {}
        if any(line.qty > 0 for line in lines):
            commerce = self._commerce()
            sellable_products = self._products_by_id(
                commerce, tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                outlet_esi_id=cart.humbee_buyer_esi_id, seller_esi_id=cart.humbee_seller_esi_id,
                district_id=_product_district_id(
                    self._outlets(), tenant_id=claims.tenant_id, cart=cart
                ),
            )
            self._enforce_po_cap(claims, cart, lines, commerce)

        for line in lines:
            existing_line = repository.get_line(
                self._session, cart_draft_id=cart.id, product_id=line.product_id
            )
            if line.qty == 0:
                # Cart rows are soft-deleted globally. qty=0 deactivates the line so list/read
                # paths drop it while re-add can reactivate the same row under the unique key.
                if existing_line is not None and existing_line.is_active:
                    existing_line.is_active = False
                    existing_line.deactivated_at = self._clock.now_utc()
                    existing_line.deactivated_by = claims.employee_id
                continue

            product = sellable_products.get(line.product_id)
            if product is None:
                raise ApiError(
                    422, "product_not_sellable", "This product is not sellable for this order."
                )
            if product.form_type_req and line.form_type is None:
                raise ApiError(
                    422, "form_type_required",
                    "Select form type (STRAIGHT or BEND) for this product.",
                )
            # stock_status is advice, never a rule (§9.2) — a product marked out_of_stock stays
            # fully orderable; what can actually be fulfilled is settled by Humbee at submission.
            line_form_type = line.form_type if product.form_type_req else None

            now = self._clock.now_utc()
            if existing_line is not None:
                existing_line.qty = line.qty
                existing_line.form_type = line_form_type
                existing_line.unit_price_net_paise = product.unit_price_net_paise
                existing_line.unit_price_as_of = now
                existing_line.is_active = True
                existing_line.deactivated_at = None
                existing_line.deactivated_by = None
            else:
                self._session.add(
                    CartLine(
                        tenant_id=claims.tenant_id, cart_draft_id=cart.id,
                        humbee_product_id=line.product_id, qty=line.qty, form_type=line_form_type,
                        unit_price_net_paise=product.unit_price_net_paise,
                        unit_price_as_of=now, created_by_employee_id=claims.employee_id,
                    )
                )
        with transaction(self._session):
            self._session.flush()
            payload = self._cart_payload(claims, cart, revalidate=False)
            self._store_idempotency(
                endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=200,
                payload=payload, tenant_id=claims.tenant_id, actor_employee_id=claims.employee_id,
            )
        return 200, payload

    # -- totals ---------------------------------------------------------------

    def _cart_payload(
        self, claims: AccessTokenClaims, cart: CartDraft, *, revalidate: bool
    ) -> dict[str, Any]:
        lines = repository.list_lines(self._session, cart_draft_id=cart.id)
        commerce = self._commerce()
        price_changed: set[str] = set()
        form_type_cleared = False
        gst_rate_by_product: dict[str, int] = {}
        products: dict[str, ProductRecord] = {}
        as_of = self._clock.now_utc()  # fallback when there is nothing to re-read

        if lines:
            products = self._products_by_id(
                commerce, tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                outlet_esi_id=cart.humbee_buyer_esi_id, seller_esi_id=cart.humbee_seller_esi_id,
                district_id=_product_district_id(
                    self._outlets(), tenant_id=claims.tenant_id, cart=cart
                ),
            )
            for line in lines:
                product = products.get(line.humbee_product_id)
                if product is None:
                    continue
                gst_rate_by_product[line.humbee_product_id] = product.gst_rate_bp
                if not product.form_type_req and line.form_type is not None:
                    line.form_type = None
                    form_type_cleared = True
                if (
                    revalidate
                    and product.unit_price_net_paise is not None
                    and product.unit_price_net_paise != line.unit_price_net_paise
                ):
                    line.unit_price_net_paise = product.unit_price_net_paise
                    line.unit_price_as_of = as_of
                    price_changed.add(line.humbee_product_id)
            if price_changed or form_type_cleared:
                self._session.flush()

        line_nets = [(line.unit_price_net_paise or 0) * line.qty for line in lines]
        subtotal_net_paise = sum(line_nets)

        scheme_discount_paise = 0
        scheme_label: str | None = None
        if lines:
            try:
                scheme = commerce.evaluate_scheme(
                    tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                    manufacturer_id=cart.humbee_manufacturer_id,
                    lines=[(line.humbee_product_id, line.qty) for line in lines],
                )
                scheme_discount_paise = min(scheme.discount_paise, subtotal_net_paise)  # R-ORD-26
                scheme_label = scheme.label
            except SchemeUnavailable:
                scheme_discount_paise = 0
                scheme_label = None

        cart.scheme_discount_paise = scheme_discount_paise
        cart.scheme_label = scheme_label
        product_discount_paise = _product_discount_paise(lines, products) if lines else 0
        cart.product_discount_paise = product_discount_paise
        if lines:
            self._session.flush()

        discount_shares = _apportion(scheme_discount_paise, line_nets) if lines else []
        line_outs: list[schemas.CartLineOut] = []
        gst_amount_paise = 0
        for line, line_net, discount_share in zip(lines, line_nets, discount_shares, strict=True):
            product = products.get(line.humbee_product_id)
            product_discount_share = (
                _line_product_discount_paise(line.unit_price_net_paise, product.discount_rate_bp, line.qty)
                if product is not None else 0
            )
            taxable = line_net - discount_share - product_discount_share
            gst_rate_bp = gst_rate_by_product.get(line.humbee_product_id, 0)
            line_gst = _basis_point_amount(taxable, gst_rate_bp)
            gst_amount_paise += line_gst
            line_outs.append(
                schemas.CartLineOut(
                    product_id=line.humbee_product_id,
                    qty=line.qty,
                    form_type=cast(Any, line.form_type),
                    unit_price_net_paise=line.unit_price_net_paise,
                    unit_price_as_of=line.unit_price_as_of, line_net_paise=line_net,
                    line_gst_amount_paise=line_gst,
                    price_changed=line.humbee_product_id in price_changed,
                )
            )

        taxable_base_paise = subtotal_net_paise - scheme_discount_paise - product_discount_paise
        gross_total_paise = taxable_base_paise + gst_amount_paise

        po = self._po_record_for_cart(claims, cart, commerce)
        po_cap_qty, po_cap_source = _po_cap(po) if po is not None else (None, None)
        po_line_balances = (
            {line.product_id: line.balance_qty for line in po.lines} if po is not None else {}
        )
        try:
            seller_name = self._resolve_seller(
                tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id, seller_id=cart.humbee_seller_id,
            ).name
        except ApiError:
            # The seller link may have gone inactive since this cart was opened; the cart is
            # still readable, just with its last-known type as a display fallback.
            seller_name = cart.seller_type_snapshot

        return schemas.CartResponse(
            id=cart.id, status=cart.status, visit_id=cart.visit_id, outlet_id=cart.humbee_outlet_id,
            manufacturer_id=cart.humbee_manufacturer_id, seller_id=cart.humbee_seller_id,
            outlet_esi_id=cart.humbee_buyer_esi_id, seller_esi_id=cart.humbee_seller_esi_id,
            seller_name=seller_name,
            order_path=cast(schemas.OrderPath, cart.order_path),
            seller_type_snapshot=cart.seller_type_snapshot, source_po_id=cart.humbee_po_id,
            ship_to_type=cart.ship_to_type, ship_to_outlet_id=cart.ship_to_humbee_outlet_id,
            ship_to_esi_id=cart.ship_to_humbee_esi_id,
            shipping_address_override=_shipping_override(
                cart.shipping_address_line1, cart.shipping_address_line2,
                cart.shipping_address_state_id, cart.shipping_address_district_id,
                cart.shipping_address_pincode,
            ),
            lines=line_outs,
            subtotal_net_paise=subtotal_net_paise, scheme_discount_paise=scheme_discount_paise,
            scheme_label=scheme_label, product_discount_paise=product_discount_paise,
            taxable_base_paise=taxable_base_paise,
            gst_amount_paise=gst_amount_paise, gross_total_paise=gross_total_paise,
            po_cap_qty=po_cap_qty, po_cap_source=cast(Any, po_cap_source),
            po_line_balances=po_line_balances,
            expires_at=cart.expires_at, as_of=as_of,
        ).model_dump(mode="json")

    # -- order context / catalogue reads --------------------------------------

    def get_order_context(
        self,
        *,
        claims: AccessTokenClaims,
        visit_id: str,
        outlet_id: str,
        manufacturer_id: str,
        seller_id: str | None = None,
        outlet_esi_id: str | None = None,
    ) -> dict[str, Any]:
        """S-ORD1 (M10 §5.1): one fan-out call. `no_sellers_linked`/`seller_selection_required`
        are first-class recovery states here — this read never raises for
        either, so the screen can render a picker or an empty state instead of an error toast."""

        outlet_ref = self._resolve_active_visit_outlet(claims, visit_id)
        if outlet_ref != outlet_id:
            raise ApiError(422, "outlet_mismatch", "The outlet does not match the active visit.")

        commerce = self._commerce()
        manufacturer = commerce.get_partner(
            tenant_id=claims.tenant_id, outlet_id=outlet_id, partner_id=manufacturer_id
        )
        brand = self._brand_sellers(
            tenant_id=claims.tenant_id, outlet_id=outlet_id, manufacturer_id=manufacturer_id
        )
        active_sellers = [s for s in (brand.sellers if brand else ()) if s.is_active]
        as_of = self._clock.now_utc()

        no_sellers_linked = not active_sellers
        seller_selection_required = bool(active_sellers) and seller_id is None and len(active_sellers) > 1
        selected_seller: SellerRecord | None = None
        if seller_id is not None:
            selected_seller = next((s for s in active_sellers if s.external_id == seller_id), None)
            if selected_seller is None:
                raise ApiError(
                    422,
                    "seller_not_linked",
                    "This seller is not linked to the outlet for this brand.",
                )
        elif len(active_sellers) == 1:
            selected_seller = active_sellers[0]

        order_path: schemas.OrderPath | None = None
        requires_approval: bool | None = None
        purchase_orders: list[PurchaseOrderRecord] = []
        ship_to_options: list[ShipToOption] = []
        banner: str | None = None
        delivery_available = True
        delivery_block_reason: str | None = None

        if selected_seller is not None:
            order_path = _order_path_for(selected_seller)
            requires_approval = selected_seller.manager_approval_required
            banner = _banner_for(selected_seller, order_path)
            buyer_esi_id, _seller_esi_id = _esi_ids_for(selected_seller)
            if outlet_esi_id is not None:
                if not any(esi.esi_id == outlet_esi_id for esi in selected_seller.outlet_esi_records):
                    raise ApiError(
                        422,
                        "buyer_esi_not_mapped",
                        "This outlet shipping ESI is not linked to the selected seller.",
                    )
                buyer_esi_id = outlet_esi_id
            if buyer_esi_id:
                ship_to_options = commerce.list_ship_to_options(
                    tenant_id=claims.tenant_id, outlet_id=outlet_id, buyer_esi_id=buyer_esi_id,
                )
            if order_path == "po_backed" and buyer_esi_id:
                purchase_orders = commerce.list_open_purchase_orders(
                    tenant_id=claims.tenant_id, outlet_id=outlet_id,
                    manufacturer_id=manufacturer_id, outlet_esi_id=buyer_esi_id,
                )
            # The outlet's district comes from the local projection, which C-2 populates with a
            # district *id*. C-3 carries only a district name, and names repeat across states, so
            # the detail call this check used to make could not identify a district at all.
            projected = self._outlets().get_projected_outlets(
                tenant_id=claims.tenant_id, outlet_ids=[outlet_id]
            )
            try:
                serviceable = self._delivers_to_district(
                    tenant_id=claims.tenant_id,
                    manufacturer_id=manufacturer_id,
                    district_id=projected[0].record.district_external_id if projected else None,
                )
            except ServiceableGeographyUnavailable:
                delivery_available = False
                delivery_block_reason = "Delivery availability could not be confirmed right now."
            else:
                if not serviceable:
                    delivery_available = False
                    delivery_block_reason = (
                        "This manufacturer does not currently deliver to this outlet's district."
                    )

        return schemas.OrderContextResponse(
            outlet_id=outlet_id, manufacturer_id=manufacturer_id, manufacturer_name=manufacturer.name,
            sellers=[
                schemas.SellerOut(
                    seller_id=s.external_id, seller_type=s.seller_type, name=s.name,
                    address=s.address,
                    requires_purchase_order=s.requires_purchase_order,
                    manager_approval_required=s.manager_approval_required,
                )
                for s in active_sellers
            ],
            sellers_filtered_by_district=bool(brand and brand.filtered_by_district),
            no_sellers_linked=no_sellers_linked,
            seller_selection_required=seller_selection_required,
            selected_seller_id=selected_seller.external_id if selected_seller else None,
            order_path=order_path, requires_approval=requires_approval,
            purchase_orders=[
                schemas.PurchaseOrderOut(
                    po_id=po.external_id, po_number=po.number, status=po.status,
                    manufacturer_id=po.manufacturer_id, manufacturer_name=po.manufacturer_name,
                    net_value_paise=po.net_value_paise, balance_value_paise=po.balance_value_paise,
                    max_dp_quantity=po.max_dp_quantity, available_quantity=po.available_quantity,
                    po_date=po.po_date, valid_until=po.valid_until,
                )
                for po in purchase_orders
            ],
            default_source_po_id=purchase_orders[0].external_id if len(purchase_orders) == 1 else None,
            ship_to_options=[
                schemas.ShipToOptionOut(
                    party_id=o.party_id, esi_id=o.esi_id, esi_code=o.esi_code, name=o.name,
                    address_line1=o.address_line1, address_line2=o.address_line2,
                    address_line3=o.address_line3, state_id=o.state_id,
                    district_id=o.district_id, pincode=o.pincode,
                    geographic_info=o.geographic_info, is_self=o.is_self,
                )
                for o in ship_to_options
            ],
            delivery_available=delivery_available, delivery_block_reason=delivery_block_reason,
            banner=banner, as_of=as_of,
        ).model_dump(mode="json")

    def get_purchase_orders(
        self,
        *,
        claims: AccessTokenClaims,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str,
    ) -> dict[str, Any]:
        """S-ORD1b (M10 §5.2): live, never cached (R-ORD-09/10)."""

        pos = self._commerce().list_open_purchase_orders(
            tenant_id=claims.tenant_id, outlet_id=outlet_id, manufacturer_id=manufacturer_id,
            outlet_esi_id=outlet_esi_id,
        )
        return schemas.PurchaseOrdersResponse(
            purchase_orders=[
                schemas.PurchaseOrderOut(
                    po_id=po.external_id, po_number=po.number, status=po.status,
                    manufacturer_id=po.manufacturer_id, manufacturer_name=po.manufacturer_name,
                    net_value_paise=po.net_value_paise, balance_value_paise=po.balance_value_paise,
                    max_dp_quantity=po.max_dp_quantity, available_quantity=po.available_quantity,
                    po_date=po.po_date, valid_until=po.valid_until,
                )
                for po in pos
            ],
            as_of=pos[0].as_of if pos else self._clock.now_utc(),
        ).model_dump(mode="json")

    def list_serviceable_states(
        self, *, claims: AccessTokenClaims, manufacturer_id: str
    ) -> dict[str, Any]:
        """Bounds the shipping-address state dropdown to where this manufacturer actually
        delivers, instead of rejecting an unserviceable pick only after `PATCH /carts/{id}`."""

        states = self._commerce().list_serviceable_states(
            tenant_id=claims.tenant_id, manufacturer_id=manufacturer_id
        )
        return schemas.ServiceableStatesResponse(
            states=[
                schemas.ServiceableStateOut(state_id=s.external_id, state_name=s.name)
                for s in states
            ]
        ).model_dump(mode="json")

    def list_serviceable_districts(
        self, *, claims: AccessTokenClaims, manufacturer_id: str, state_id: str
    ) -> dict[str, Any]:
        """Bounds the shipping-address district dropdown, once a state has been picked from
        `list_serviceable_states`."""

        districts = self._commerce().list_serviceable_districts(
            tenant_id=claims.tenant_id, manufacturer_id=manufacturer_id, state_id=state_id
        )
        return schemas.ServiceableDistrictsResponse(
            districts=[
                schemas.ServiceableDistrictOut(district_id=d.external_id, district_name=d.name)
                for d in districts
            ]
        ).model_dump(mode="json")

    def get_catalog(
        self, *, claims: AccessTokenClaims, cart_id: str, query: str | None, category: str | None
    ) -> dict[str, Any]:
        """S-ORD2 (M10 §5.3). Price and stock are fields on the same product read (§8.1) — there
        is no separate stock capability to degrade independently any more; a null `stock_status`
        renders as unknown, never `0`/"out of stock" (R-ORD-17)."""

        cart = self._own_cart(claims, cart_id)
        commerce = self._commerce()
        try:
            products = commerce.list_products(
                tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                outlet_esi_id=cart.humbee_buyer_esi_id, seller_esi_id=cart.humbee_seller_esi_id,
                district_id=_product_district_id(
                    self._outlets(), tenant_id=claims.tenant_id, cart=cart
                ),
                po_id=cart.humbee_po_id, category=category, query=query,
            )
        except CommerceUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Commerce data is unavailable right now."
            ) from exc

        qty_by_product = {
            line.humbee_product_id: line.qty
            for line in repository.list_lines(self._session, cart_draft_id=cart.id)
        }
        cart_subtotal_net_paise = sum(
            (p.unit_price_net_paise or 0) * qty_by_product.get(p.external_id, 0)
            for p in products
        )

        return schemas.CatalogResponse(
            products=[
                schemas.CatalogProductOut(
                    product_id=p.external_id, name=p.name, category=p.category_name or p.category_id,
                    image_url=p.image_url,
                    category_id=p.category_id, category_name=p.category_name,
                    pack_size=None, uom=p.uom, multiplier=p.multiplier,
                    unit_price_net_paise=p.unit_price_net_paise,
                    discount_rate_bp=p.discount_rate_bp, gst_rate_bp=p.gst_rate_bp,
                    stock_status=p.stock_status, form_type_req=p.form_type_req,
                    qty_in_cart=qty_by_product.get(p.external_id, 0),
                )
                for p in products
            ],
            cart_item_count=sum(1 for qty in qty_by_product.values() if qty > 0),
            cart_subtotal_net_paise=cart_subtotal_net_paise,
            as_of=self._clock.now_utc(),
        ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Order submission — Story 4.2 (dealer/direct) + 4.3 (DP/po_backed), M10 §5.5, §5.9.
# `submit_to_humbee` calls Humbee synchronously (no outbox handoff); the Humbee client itself
# retries transient failures with jittered exponential backoff (integration/humbee/commerce.py).
# ---------------------------------------------------------------------------


def append_status_event(
    session: Session,
    order: Order,
    *,
    kind: str,
    title: str,
    detail: str | None,
    occurred_at: datetime,
    timeline_state: str,
    actor_employee_id: str | None = None,
    attempt_id: str | None = None,
    visible_to_sp: bool = True,
) -> None:
    """One append-only `OrderStatusEvent` row (M10 §3.8). `seq` is derived, never client-supplied,
    so the timeline stays gap-free under concurrent writers."""

    seq = repository.next_status_event_seq(session, order_id=order.id)
    session.add(
        StatusEvent(
            tenant_id=order.tenant_id, order_id=order.id, seq=seq, kind=kind, title=title,
            detail=detail, occurred_at=occurred_at, timeline_state=timeline_state,
            actor_employee_id=actor_employee_id, attempt_id=attempt_id,
            visible_to_sp=visible_to_sp, created_by_employee_id=actor_employee_id,
        )
    )
    session.flush()


def submit_to_humbee(
    session: Session,
    *,
    order: Order,
    clock: Clock,
    settings: Settings,
    trigger: str,
    triggered_by_employee_id: str | None = None,
) -> None:
    """Registers `order` with Humbee synchronously: writes a fresh `SubmissionAttempt` row, calls
    `commerce.register_order` (itself retried with exponential backoff up to 3 total attempts —
    integration/humbee/commerce.py), and resolves the attempt/order on success or failure exactly
    as the former outbox-drain path did. Never commits or rolls back; the caller owns the
    transaction — this runs from both the submit/retry endpoints and `DpOrderAdapter.on_approved`,
    the latter inside the approvals engine's own decision transaction.

    `trigger` stays one of the values `orders_attempt_trigger_chk` already allows (still
    `outbox_auto` for the approval/auto-approve path) so this change needs no schema migration.
    """

    now = clock.now_utc()
    previous = repository.latest_attempt(session, order_id=order.id)
    attempt = SubmissionAttempt(
        tenant_id=order.tenant_id, order_id=order.id,
        attempt_no=(previous.attempt_no + 1 if previous else 1), trigger=trigger,
        triggered_by_employee_id=triggered_by_employee_id,
        request_idempotency_key=order.order_number,  # identical across every retry of this order
        request_payload_hash=_fingerprint(
            json.dumps({"order_id": order.id}, sort_keys=True).encode()
        ),
        started_at=now, trace_id=generate_ulid(), created_by_employee_id=triggered_by_employee_id,
    )
    session.add(attempt)
    order.status = "dp_creation_pending"
    order.sub_status_reason = None
    session.flush()
    append_status_event(
        session, order, kind="dp_creation_started", title="Creating DP order",
        detail="Within one hour of approval" if order.dp_sla_deadline_at else None,
        occurred_at=now, timeline_state="current", attempt_id=attempt.id,
    )

    commerce = HumbeeCommerceProvider(settings)
    lines = repository.list_order_lines(session, order_id=order.id)
    # Legacy rows created before approved-baseline persistence can still carry null approved
    # fields. Materialize baseline values once before building the outbound payload.
    for line in lines:
        approved_qty = (
            line.approved_qty if line.approved_qty is not None else line.requested_qty
        )
        if line.approved_qty is None:
            line.approved_qty = approved_qty
        if line.approved_line_net_paise is None:
            line.approved_line_net_paise = (line.unit_price_net_paise or 0) * approved_qty
        if line.approved_line_gst_amount_paise is None:
            line.approved_line_gst_amount_paise = line.line_gst_amount_paise

    started = attempt.started_at

    try:
        result = commerce.register_order(
            tenant_id=order.tenant_id, idempotency_key=order.order_number,
            outlet_id=order.humbee_outlet_id, manufacturer_id=order.humbee_manufacturer_id,
            buyer_esi_id=order.humbee_buyer_esi_id,
            seller_id=order.humbee_seller_id, seller_esi_id=order.humbee_seller_esi_id,
            source_po_id=order.humbee_po_id,
            ship_to_outlet_id=order.ship_to_humbee_outlet_id,
            ship_to_esi_id=order.ship_to_humbee_esi_id,
            requested_district_id=order.shipping_address_district_id,
            requested_pincode=order.shipping_address_pincode,
            lines=[
                RegisterOrderLine(
                    product_id=line.humbee_product_id,
                    quantity_in_uom=(
                        line.approved_qty if line.approved_qty is not None else line.requested_qty
                    ),
                    bundle=0,
                    remark="",
                    form_type=cast(Any, line.form_type),
                )
                for line in lines
            ],
            source="sfa", sfa_order_reference=order.order_number, placed_by=order.employee_id,
            approved_by=order.approver_employee_id_snapshot, occurred_at=order.occurred_at,
        )
    except OrderRegistrationFailed as exc:
        completed = clock.now_utc()
        attempt.completed_at = completed
        attempt.duration_ms = int((completed - started).total_seconds() * 1000)
        attempt.outcome = "timeout" if exc.failure_class == "timeout" else "failed_terminal"
        attempt.failure_class = exc.failure_class
        attempt.humbee_error_message = str(exc)
        attempt.sfa_display_reason = _FAILURE_REASON_BY_CLASS.get(
            exc.failure_class, f"Humbee rejected the order: {exc}"
        )
        order.sub_status_reason = attempt.sfa_display_reason
        order.status = "submission_failed"
        if order.retry_budget_remaining > 0:
            order.retry_budget_remaining -= 1
        append_status_event(
            session, order, kind="dp_creation_attempt_failed", title="PO/DP submission failed",
            detail=attempt.humbee_error_message, occurred_at=completed, timeline_state="rejected",
            attempt_id=attempt.id,
        )
        return

    completed = clock.now_utc()
    attempt.completed_at = completed
    attempt.duration_ms = int((completed - started).total_seconds() * 1000)
    attempt.outcome = "success"
    attempt.downstream_dp_order_ref = result.dp_order_ref
    attempt.humbee_accepted_gross_total_paise = result.accepted_gross_total_paise
    order.status = "dp_created"
    order.downstream_dp_order_ref = result.dp_order_ref
    order.dp_created_at = completed

    # a missing total on either side is "not checked", never crashed on or absorbed as a match
    approved_total = (
        order.approved_gross_total_paise
        if order.approved_gross_total_paise is not None
        else order.gross_total_paise
    )
    accepted_total = result.accepted_gross_total_paise
    if accepted_total is not None and approved_total is not None and accepted_total != approved_total:
        order.sub_status_reason = (
            f"Amount discrepancy: Humbee accepted {accepted_total} paise, "
            f"approved total was {approved_total} paise."
        )
        attempt.sfa_display_reason = order.sub_status_reason
        append_status_event(
            session, order, kind="amount_discrepancy", title="Amount mismatch on acceptance",
            detail=order.sub_status_reason, occurred_at=completed, timeline_state="current",
            attempt_id=attempt.id,
        )

    append_status_event(
        session, order, kind="dp_created", title="Sent to PO/DP", detail=result.dp_order_ref,
        occurred_at=completed, timeline_state="done", attempt_id=attempt.id,
    )


@dataclass(frozen=True)
class OrderReportingProjection:
    """The slice `reporting.producers.orders_rollup` needs — a background fold reading the
    order's *current* state directly, rather than only what an event payload happened to carry.
    Fixes the gap where orders submitted before `order_submitted` carried enough payload (or
    submitted at all) would otherwise never contribute to the fact tables."""

    id: str
    employee_id: str
    humbee_outlet_id: str
    humbee_manufacturer_id: str
    manufacturer_name_snapshot: str
    business_date: date
    status: str
    requires_approval: bool
    approved_gross_value_paise: int
    lines_count: int
    approved_lines_count: int
    approved_qty_by_uom: dict[str, int]


def _to_reporting_projection(order: Order, *, lines: list[OrderLine]) -> OrderReportingProjection:
    approved_qty_by_uom: dict[str, int] = {}
    approved_lines_count = 0
    for line in lines:
        if line.approved_qty is not None:
            approved_lines_count += 1
            if line.approved_qty > 0:
                approved_qty_by_uom[line.uom_snapshot] = (
                    approved_qty_by_uom.get(line.uom_snapshot, 0) + line.approved_qty
                )
    approved_gross_value_paise = (
        order.approved_gross_total_paise
        if order.approved_gross_total_paise is not None
        else order.gross_total_paise
    )
    return OrderReportingProjection(
        id=order.id,
        employee_id=order.employee_id,
        humbee_outlet_id=order.humbee_outlet_id,
        humbee_manufacturer_id=order.humbee_manufacturer_id,
        manufacturer_name_snapshot=order.manufacturer_name_snapshot,
        business_date=order.business_date,
        status=order.status,
        requires_approval=order.requires_approval,
        approved_gross_value_paise=approved_gross_value_paise,
        lines_count=len(lines),
        approved_lines_count=approved_lines_count,
        approved_qty_by_uom=approved_qty_by_uom,
    )


def get_order_reporting_fields(
    session: Session, *, tenant_id: str, order_id: str
) -> OrderReportingProjection | None:
    """Read-model fields for the reporting orders producer. No claims/scope — the caller is a
    background fold already holding authority via the domain event it is processing, not an
    actor whose access needs checking."""

    order = repository.get_order(session, tenant_id=tenant_id, order_id=order_id)
    if order is None:
        return None
    lines = repository.list_order_lines(session, order_id=order_id)
    return _to_reporting_projection(order, lines=lines)


def list_order_reporting_fields_for_day(
    session: Session, *, tenant_id: str, employee_id: str, business_date: date
) -> list[OrderReportingProjection]:
    """Every order an employee submitted on one business date, for the reporting orders
    producer's day-recompute (M11 §3b.3 rule 2: recompute the full day, never increment)."""

    orders = repository.list_orders_for_employee_day(
        session, tenant_id=tenant_id, employee_id=employee_id, business_date=business_date
    )
    return [
        _to_reporting_projection(
            order, lines=repository.list_order_lines(session, order_id=order.id)
        )
        for order in orders
    ]


def list_order_reporting_employee_days(
    session: Session, *, tenant_id: str
) -> list[tuple[str, date]]:
    """Distinct `(employee_id, business_date)` pairs that have orders — enumerator for the
    reporting manufacturer/district backfill. No claims/scope: the caller is a background
    fold, not an actor whose access needs checking."""

    return repository.list_order_employee_days(session, tenant_id=tenant_id)


class OrderService:
    """Cart → `Order` submission and reads. Extends `CartService`'s cart primitives rather than
    duplicating them — the cart already produces the grouped, priced, snapshotted lines this
    freezes onto the order (M10 §3.3 "preserve submitted commercial snapshots")."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        clock: Clock | None = None,
        outlet_port: HumbeeOutletMasterProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._clock = clock or SystemClock()
        self._outlet_port = outlet_port
        self._idempotency = IdempotencyService(session)
        self._events = DomainEventPublisher(session, self._clock)

    def _outlets(self) -> OutletReadService:
        return OutletReadService(
            self._session,
            settings=self._settings,
            clock=self._clock,
            outlet_port=self._outlet_port,
        )

    def _commerce(self) -> HumbeeCommerceProvider:
        try:
            return HumbeeCommerceProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(
                503, "upstream_unavailable", "Commerce data is unavailable right now."
            ) from exc

    def _sellers(self) -> HumbeeSellerLinkageProvider:
        try:
            return HumbeeSellerLinkageProvider(self._settings)
        except RuntimeError as exc:
            raise ApiError(503, "upstream_unavailable", "Seller data is unavailable right now.") from exc

    def _check_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, tenant_id: str
    ) -> tuple[int, dict[str, Any]] | None:
        self._idempotency.claim(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key
        )
        existing = self._idempotency.get(tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key)
        if existing is None:
            return None
        if not self._idempotency.is_exact_replay(existing, _fingerprint(raw_body)):
            raise ApiError(
                409, "idempotency_conflict", "Idempotency key was already used with a different payload."
            )
        return existing.status_code, existing.response_payload

    def _store_idempotency(
        self, *, endpoint: str, idempotency_key: str, raw_body: bytes, status_code: int,
        payload: dict[str, Any], tenant_id: str, actor_employee_id: str,
    ) -> None:
        self._idempotency.save(
            tenant_id=tenant_id, endpoint=endpoint, key=idempotency_key,
            request_fingerprint=_fingerprint(raw_body),
            response_fingerprint=_fingerprint(json.dumps(payload, sort_keys=True, default=str).encode()),
            status_code=status_code, response_payload=payload, actor_employee_id=actor_employee_id,
        )

    def _own_cart(self, claims: AccessTokenClaims, cart_id: str) -> CartDraft:
        cart = repository.get_cart(self._session, tenant_id=claims.tenant_id, cart_id=cart_id)
        if cart is None or cart.employee_id != claims.employee_id:
            raise ApiError(404, "cart_not_found", "Cart was not found.")
        return cart

    def _own_order(self, claims: AccessTokenClaims, order_id: str) -> Order:
        order = repository.get_order_by_id_or_cart(
            self._session, tenant_id=claims.tenant_id, order_id=order_id
        )
        if order is None or order.employee_id != claims.employee_id:
            raise ApiError(404, "order_not_found", "Order was not found.")
        return order

    # -- pricing (re-freezes at submission — cart prices are advisory, M10 §3.3) --------------

    def _price_order_lines(
        self, *, tenant_id: str, cart: CartDraft, cart_lines: list[CartLine]
    ) -> tuple[list[dict[str, Any]], int, int, int, int, int, str | None, datetime]:
        commerce = self._commerce()
        try:
            products = {
                p.external_id: p
                for p in commerce.list_products(
                    tenant_id=tenant_id, outlet_id=cart.humbee_outlet_id,
                    manufacturer_id=cart.humbee_manufacturer_id,
                    outlet_esi_id=cart.humbee_buyer_esi_id, seller_esi_id=cart.humbee_seller_esi_id,
                    district_id=_product_district_id(
                        self._outlets(), tenant_id=tenant_id, cart=cart
                    ),
                    po_id=cart.humbee_po_id, category=None, query=None,
                )
            }
        except CommerceUnavailable as exc:
            raise ApiError(
                503, "upstream_unavailable", "Commerce data is unavailable right now."
            ) from exc
        as_of = self._clock.now_utc()
        line_nets: list[int] = []
        for cart_line in cart_lines:
            product = products.get(cart_line.humbee_product_id)
            if product is None:
                raise ApiError(
                    422, "product_not_sellable", "A cart line is no longer sellable."
                )
            if product.form_type_req and cart_line.form_type is None:
                raise ApiError(
                    422, "form_type_required",
                    "Select form type (STRAIGHT or BEND) for all required products.",
                )
            line_nets.append((product.unit_price_net_paise or 0) * cart_line.qty)
        subtotal_net_paise = sum(line_nets)

        scheme_discount_paise = cart.scheme_discount_paise
        scheme_label = cart.scheme_label
        try:
            scheme = commerce.evaluate_scheme(
                tenant_id=tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                lines=[(cl.humbee_product_id, cl.qty) for cl in cart_lines],
            )
            scheme_discount_paise = min(scheme.discount_paise, subtotal_net_paise)
            scheme_label = scheme.label
        except SchemeUnavailable:
            scheme_discount_paise = min(cart.scheme_discount_paise, subtotal_net_paise)
            scheme_label = cart.scheme_label if scheme_discount_paise > 0 else None

        cart.scheme_discount_paise = scheme_discount_paise
        cart.scheme_label = scheme_label
        self._session.flush()

        discount_shares = _apportion(scheme_discount_paise, line_nets)
        line_data: list[dict[str, Any]] = []
        gst_amount_paise = 0
        product_discount_paise = 0
        for line_no, (cart_line, line_net, discount_share) in enumerate(
            zip(cart_lines, line_nets, discount_shares, strict=True), start=1
        ):
            product = products[cart_line.humbee_product_id]
            # Re-priced from the live `product.unit_price_net_paise`, the same basis line_net uses
            # here — not the cart line's (possibly stale) snapshot.
            product_discount_share = _line_product_discount_paise(
                product.unit_price_net_paise, product.discount_rate_bp, cart_line.qty
            )
            product_discount_paise += product_discount_share
            taxable = line_net - discount_share - product_discount_share
            line_gst = _basis_point_amount(taxable, product.gst_rate_bp)
            gst_amount_paise += line_gst
            line_data.append(
                {
                    "line_no": line_no, "product_id": cart_line.humbee_product_id,
                    "product_name": product.name, "category": product.category_name or product.category_id,
                    "uom": product.uom,
                    "manufacturer_id": cart.humbee_manufacturer_id,
                    "gst_rate_bp": product.gst_rate_bp,
                    "unit_price_net_paise": product.unit_price_net_paise,
                    "unit_price_as_of": as_of, "qty": cart_line.qty,
                    "form_type": cart_line.form_type,
                    "line_net_paise": line_net, "line_gst_amount_paise": line_gst,
                    "scheme_discount_paise": discount_share,
                    "product_discount_paise": product_discount_share,
                    "stock_status": product.stock_status,
                }
            )
        cart.product_discount_paise = product_discount_paise

        taxable_base_paise = subtotal_net_paise - scheme_discount_paise - product_discount_paise
        gross_total_paise = taxable_base_paise + gst_amount_paise
        cart.gross_total_paise = gross_total_paise
        return (
            line_data, subtotal_net_paise, scheme_discount_paise, taxable_base_paise,
            gst_amount_paise, gross_total_paise, scheme_label, as_of,
        )

    # -- submission ------------------------------------------------------------------------

    def submit_order(
        self, *, claims: AccessTokenClaims, body: schemas.SubmitOrderBody,
        idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """S-ORD4 submit (M10 §5.5). One transaction: re-verify the seller live, freeze the
        snapshot, route (auto-approve / open a generic approval request), submit to Humbee
        synchronously when no approval is needed, and close the originating visit exactly once."""

        endpoint = "POST /orders"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=claims.tenant_id,
        )
        if replay is not None:
            return replay

        cart = self._own_cart(claims, body.cart_id)
        if cart.status != "open":
            raise ApiError(409, "cart_not_open", "This cart is no longer open.")
        cart_lines = repository.list_lines(self._session, cart_draft_id=cart.id)
        if not cart_lines:
            raise ApiError(422, "cart_empty", "Add at least one line before submitting.")  # R-ORD-19
        cart_revision = cart.updated_at
        line_revisions = tuple(sorted((line.id, line.updated_at) for line in cart_lines))

        commerce = self._commerce()
        try:
            snapshot = self._sellers().get_outlet_sellers(
                tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id
            )
        except SellerLinkageUnavailable as exc:
            raise ApiError(503, "upstream_unavailable", "Seller data is unavailable right now.") from exc
        brand = next((b for b in snapshot.brands if b.brand_id == cart.humbee_manufacturer_id), None)
        seller = next(
            (s for s in (brand.sellers if brand else ()) if s.external_id == cart.humbee_seller_id),
            None,
        )
        if seller is None or not seller.is_active:
            # R-ORD-04: a mid-flight change to the seller relationship must never silently change
            # whether a human sees this order.
            raise ApiError(
                409, "seller_relationship_changed", "This outlet's seller relationship changed. "
                "Review the order again.",
            )
        order_path = _order_path_for(seller)
        if order_path != cart.order_path:
            raise ApiError(
                409, "seller_relationship_changed",
                "This outlet's seller relationship changed. Review the order again.",
            )

        po_record = None
        if order_path == "po_backed":
            if not cart.humbee_po_id:
                raise ApiError(422, "po_required", "Select a purchase order before submitting.")
            pos = commerce.list_open_purchase_orders(
                tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
                manufacturer_id=cart.humbee_manufacturer_id,
                outlet_esi_id=cart.humbee_buyer_esi_id,
            )
            po_record = next((po for po in pos if po.external_id == cart.humbee_po_id), None)
            if po_record is None:
                raise ApiError(409, "po_no_longer_open", "This purchase order is no longer open.")
            for cart_line in cart_lines:
                line_balance = _po_line_balance(po_record, cart_line.humbee_product_id)
                if line_balance is not None and cart_line.qty > line_balance:
                    raise ApiError(
                        422, "po_line_quantity_exceeded",
                        f"This product needs {cart_line.qty} units, more than the {line_balance} "
                        "still available on the purchase order.",
                    )
            po_cap_qty, _ = _po_cap(po_record)
            total_qty = sum(line.qty for line in cart_lines)
            if po_cap_qty is not None and total_qty > po_cap_qty:
                raise ApiError(
                    422, "po_quantity_exceeded",
                    f"This order needs {total_qty} units, more than the {po_cap_qty} still "
                    "available on the purchase order.",
                )

        (
            line_data, subtotal_net_paise, scheme_discount_paise, taxable_base_paise,
            gst_amount_paise, gross_total_paise, scheme_label, as_of,
        ) = self._price_order_lines(tenant_id=claims.tenant_id, cart=cart, cart_lines=cart_lines)

        manufacturer = commerce.get_partner(
            tenant_id=claims.tenant_id, outlet_id=cart.humbee_outlet_id,
            partner_id=cart.humbee_manufacturer_id,
        )
        outlet_record = self._outlets().refresh_outlet(
            tenant_id=claims.tenant_id,
            outlet_id=cart.humbee_outlet_id,
            actor_employee_id=claims.employee_id,
        )
        if outlet_record is None:
            raise ApiError(422, "outlet_not_found", "This outlet could not be resolved.")

        # The projection refresh is staged, not committed; it lands with the order below. From
        # here to that commit there are no upstream waits.
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=claims.tenant_id,
        )
        if replay is not None:
            return replay
        cart = self._own_cart(claims, body.cart_id)
        if cart.status != "open":
            raise ApiError(409, "cart_not_open", "This cart is no longer open.")
        cart_lines = repository.list_lines(self._session, cart_draft_id=cart.id)
        if (
            cart.updated_at != cart_revision
            or tuple(sorted((line.id, line.updated_at) for line in cart_lines)) != line_revisions
        ):
            raise ApiError(409, "cart_changed", "The cart changed while the order was being checked.")

        now = self._clock.now_utc()
        occurred_at = body.occurred_at or now
        order_id = generate_ulid()
        order_number = f"SFA-ORD-{order_id[-10:]}"

        requires_approval = seller.manager_approval_required
        approval_request_id: str | None = None
        approver_employee_id: str | None = None
        approver_name: str | None = None
        approved_at: datetime | None = None
        auto_approved_at_create = False
        status = "approved"

        if requires_approval:
            request = approvals_service.create(
                self._session, tenant_id=claims.tenant_id, subject_type=str(SubjectType.DP_ORDER),
                # The approval subject is the CART, not the order — the order cannot exist yet
                # (`orders_approval_handle_chk` requires `approval_request_id` at INSERT time, one
                # statement before this call can hand one back). `DpOrderAdapter` resolves the real
                # order via `Order.cart_draft_id`. See `orders/adapter.py`.
                subject_id=cart.id, requester_id=claims.employee_id, clock=self._clock,
            )
            approval_request_id = request.id
            approver_employee_id = request.assigned_approver_id
            if approver_employee_id:
                approver = org_service.get_employee(
                    self._session, tenant_id=claims.tenant_id, employee_id=approver_employee_id
                )
                approver_name = approver.full_name
            if request.status == ApprovalStatus.AUTO_APPROVED:
                # Edge case (M06 §3b.2 Case A/C1): requester has no manager above them. The
                # generic engine's `on_approved` ran already, inside `create()`, before an order
                # row existed for it to find (`DpOrderAdapter.on_approved` no-ops in that case) —
                # finish the approval here instead.
                approved_at = request.decided_at or now
                auto_approved_at_create = True
            else:
                status = "pending_approval"
        else:
            approved_at = now

        order = Order(
            id=order_id, tenant_id=claims.tenant_id, order_number=order_number,
            order_path=order_path, seller_type_snapshot=seller.seller_type, status=status,
            cart_draft_id=cart.id, employee_id=claims.employee_id, visit_id=cart.visit_id,
            humbee_outlet_id=cart.humbee_outlet_id, outlet_name_snapshot=outlet_record.name,
            outlet_locality_snapshot=outlet_record.locality,
            humbee_manufacturer_id=cart.humbee_manufacturer_id,
            manufacturer_name_snapshot=manufacturer.name,
            humbee_seller_id=seller.external_id, seller_name_snapshot=seller.name,
            humbee_buyer_esi_id=cart.humbee_buyer_esi_id,
            humbee_seller_esi_id=cart.humbee_seller_esi_id,
            humbee_po_id=cart.humbee_po_id, ship_to_type=cart.ship_to_type,
            ship_to_humbee_outlet_id=cart.ship_to_humbee_outlet_id,
            ship_to_humbee_esi_id=cart.ship_to_humbee_esi_id,
            ship_to_label_snapshot=(
                outlet_record.name if cart.ship_to_type != "dealer" else cart.ship_to_humbee_outlet_id
            ),
            shipping_address_line1=cart.shipping_address_line1,
            shipping_address_line2=cart.shipping_address_line2,
            shipping_address_state_id=cart.shipping_address_state_id,
            shipping_address_district_id=cart.shipping_address_district_id,
            shipping_address_pincode=cart.shipping_address_pincode,
            seller_confirmed_live=True, snapshot_taken_at=now, snapshot_source_as_of=as_of,
            requires_approval=requires_approval, approval_request_id=approval_request_id,
            approver_employee_id_snapshot=approver_employee_id,
            approver_name_snapshot=approver_name, approved_at=approved_at,
            subtotal_net_paise=subtotal_net_paise, scheme_discount_paise=scheme_discount_paise,
            scheme_label_snapshot=scheme_label, product_discount_paise=cart.product_discount_paise,
            taxable_base_paise=taxable_base_paise, gst_amount_paise=gst_amount_paise,
            gross_total_paise=gross_total_paise, idempotency_key=idempotency_key,
            occurred_at=occurred_at, received_at=now, business_date=to_business_date(occurred_at),
            created_by_employee_id=claims.employee_id,
        )
        if requires_approval and auto_approved_at_create and approved_at is not None:
            order.dp_sla_deadline_at = approved_at + DP_SLA
        # Otherwise unset: the DP path's SLA clock starts at approval (T06/T07), not before, and
        # a no-approval path has no SLA clock at all (M10 §3a).
        self._session.add(order)
        self._session.flush()

        for line in line_data:
            self._session.add(
                OrderLine(
                    tenant_id=claims.tenant_id, order_id=order.id, line_no=line["line_no"],
                    humbee_product_id=line["product_id"], product_name_snapshot=line["product_name"],
                    category_snapshot=line["category"], form_type=line["form_type"],
                    uom_snapshot=line["uom"],
                    humbee_manufacturer_id_snapshot=line["manufacturer_id"],
                    gst_rate_bp=line["gst_rate_bp"],
                    price_source="price_master", humbee_po_line_id=None,
                    unit_price_net_paise=line["unit_price_net_paise"],
                    unit_price_as_of=line["unit_price_as_of"],
                    requested_qty=line["qty"],
                    approved_qty=line["qty"],
                    line_net_paise=line["line_net_paise"],
                    line_gst_amount_paise=line["line_gst_amount_paise"],
                    approved_line_net_paise=line["line_net_paise"],
                    approved_line_gst_amount_paise=line["line_gst_amount_paise"],
                    stock_status_at_add=line["stock_status"] or "unavailable",
                    scheme_line_discount_paise=line["scheme_discount_paise"],
                    product_line_discount_paise=line["product_discount_paise"],
                    created_by_employee_id=claims.employee_id,
                )
            )

        if order_path == "po_backed" and po_record is not None:
            self._session.add(
                PoReference(
                    tenant_id=claims.tenant_id, order_id=order.id, humbee_po_id=po_record.external_id,
                    po_number_snapshot=po_record.number, po_status_snapshot=po_record.status,
                    po_manufacturer_id_snapshot=po_record.manufacturer_id,
                    po_manufacturer_name_snapshot=po_record.manufacturer_name,
                    po_date_snapshot=po_record.po_date, po_valid_until_snapshot=po_record.valid_until,
                    po_payment_terms_snapshot=po_record.payment_terms,
                    po_credit_days_snapshot=po_record.credit_days,
                    po_net_value_paise_snapshot=po_record.net_value_paise,
                    po_balance_value_paise_snapshot=po_record.balance_value_paise,
                    po_as_of=po_record.as_of, created_by_employee_id=claims.employee_id,
                )
            )

        append_status_event(
            self._session, order, kind="submitted", title="Submitted", detail=None,
            occurred_at=now, timeline_state="done", actor_employee_id=claims.employee_id,
        )
        if requires_approval and status == "pending_approval":
            append_status_event(
                self._session, order, kind="approval_requested",
                title=f"Awaiting approval from {approver_name}" if approver_name else "Awaiting approval",
                detail=None, occurred_at=now, timeline_state="current",
            )
        elif requires_approval and auto_approved_at_create:
            append_status_event(
                self._session, order, kind="approved", title="Approved",
                detail="No approver above you; auto-approved.", occurred_at=now, timeline_state="done",
            )
        else:
            append_status_event(
                self._session, order, kind="approved", title="No approval required",
                detail=None, occurred_at=now, timeline_state="done",
            )

        cart.status = "converted"
        cart.converted_order_id = order.id
        self._session.flush()

        if order.status == "approved":
            submit_to_humbee(
                self._session, order=order, clock=self._clock, settings=self._settings,
                trigger="outbox_auto",
            )

        payload = self._order_payload(order, include_lines=True)
        self._store_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=202,
            payload=payload, tenant_id=claims.tenant_id, actor_employee_id=claims.employee_id,
        )
        events.publish_order_event(
            self._events,
            tenant_id=claims.tenant_id,
            event_type=events.ORDER_SUBMITTED,
            aggregate_id=order.id,
            payload={"order_id": order.id, "employee_id": order.employee_id},
            actor_employee_id=claims.employee_id,
            occurred_at=order.occurred_at,
        )
        # Deliberate exception: submit_to_humbee already made the network call to Humbee inside
        # this transaction (see its docstring), so this commit is the durability commit that makes
        # that outcome stick — not a hand-rolled replacement for `transaction()`.
        self._session.commit()
        return 202, payload

    def retry_submission(
        self, *, claims: AccessTokenClaims, order_id: str, idempotency_key: str, raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """S-ORD7 "Retry submission" (M10 §3b.6 T14). Approval is never re-requested — the manager
        already decided; this re-attempts registration with Humbee synchronously."""

        endpoint = f"POST /orders/{order_id}/retry-submission"
        replay = self._check_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body,
            tenant_id=claims.tenant_id,
        )
        if replay is not None:
            return replay

        order = self._own_order(claims, order_id)
        if order.status != "submission_failed":
            raise ApiError(409, "retry_not_allowed", "This order is not in a failed state.")

        last_attempt = repository.latest_attempt(self._session, order_id=order.id)
        if last_attempt is not None and last_attempt.failure_class in _MANUAL_RETRY_BLOCKED_CLASSES:
            raise ApiError(
                409, "retry_not_allowed",
                "This failure requires a new order, not a resubmission.",
            )
        if (
            last_attempt is not None
            and last_attempt.trigger == "manual_sp_retry"
            and last_attempt.completed_at is not None
            and self._clock.now_utc() - last_attempt.completed_at < MANUAL_RETRY_COOLDOWN
        ):
            raise ApiError(
                429, "retry_rate_limited", "Wait a few minutes before retrying again.",
            )

        submit_to_humbee(
            self._session, order=order, clock=self._clock, settings=self._settings,
            trigger="manual_sp_retry", triggered_by_employee_id=claims.employee_id,
        )
        payload = self._order_payload(order, include_lines=True)
        self._store_idempotency(
            endpoint=endpoint, idempotency_key=idempotency_key, raw_body=raw_body, status_code=202,
            payload=payload, tenant_id=claims.tenant_id, actor_employee_id=claims.employee_id,
        )
        events.publish_order_event(
            self._events,
            tenant_id=claims.tenant_id,
            event_type=events.DP_ORDER_APPROVED,
            aggregate_id=order.id,
            payload={"order_id": order.id, "status": order.status},
            actor_employee_id=claims.employee_id,
        )
        # Deliberate exception: submit_to_humbee already made the network call to Humbee inside
        # this transaction (see its docstring), so this commit is the durability commit that makes
        # that outcome stick — not a hand-rolled replacement for `transaction()`.
        self._session.commit()
        return 202, payload

    # -- reads (S-ORD6/S-ORD7/S-ORD7-M) -----------------------------------------------------

    def list_orders(
        self, *, claims: AccessTokenClaims, status: str | None, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        orders = repository.list_orders(
            self._session, scope=scope, status=status, cursor=cursor, limit=limit
        )
        return schemas.OrderListResponse(
            items=[self._order_summary(order) for order in orders],
            next_cursor=orders[-1].id if len(orders) == limit else None,
        ).model_dump(mode="json")

    def attention_signals(self, *, claims: AccessTokenClaims, business_date: date) -> dict[str, Any]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        current_start = business_date.replace(day=1)
        previous_start = _previous_month_start(current_start)
        previous_end = current_start - timedelta(days=1)
        previous_pairs = repository.list_ordered_outlet_manufacturers(
            self._session,
            scope=scope,
            from_date=previous_start,
            to_date=previous_end,
            statuses=_ORDERED_STATUSES,
        )
        current_pairs = repository.list_ordered_outlet_manufacturers(
            self._session,
            scope=scope,
            from_date=current_start,
            to_date=business_date,
            statuses=_ORDERED_STATUSES,
        )
        previous_by_manufacturer: dict[str, tuple[str, set[str]]] = {}
        for manufacturer_id, manufacturer_name, outlet_id in previous_pairs:
            name, outlets = previous_by_manufacturer.get(manufacturer_id, (manufacturer_name, set()))
            outlets.add(outlet_id)
            previous_by_manufacturer[manufacturer_id] = (manufacturer_name or name, outlets)
        current_by_manufacturer: dict[str, set[str]] = {}
        for manufacturer_id, _, outlet_id in current_pairs:
            current_by_manufacturer.setdefault(manufacturer_id, set()).add(outlet_id)
        dropoff: dict[str, Any] | None = None
        for manufacturer_id, (manufacturer_name, previous_outlets) in previous_by_manufacturer.items():
            stopped = previous_outlets - current_by_manufacturer.get(manufacturer_id, set())
            if not stopped:
                continue
            candidate = {
                "manufacturer_id": manufacturer_id,
                "manufacturer_name": manufacturer_name,
                "outlet_count": len(stopped),
                "previous_month_label": previous_start.strftime("%B"),
                "current_month_label": current_start.strftime("%B"),
            }
            if dropoff is None or candidate["outlet_count"] > dropoff["outlet_count"]:
                dropoff = candidate
            elif candidate["outlet_count"] == dropoff["outlet_count"] and manufacturer_name < dropoff["manufacturer_name"]:
                dropoff = candidate
        return {
            "failed_count": repository.count_orders(
                self._session, scope=scope, status="submission_failed"
            ),
            "dropoff": dropoff,
        }

    def get_order(self, *, claims: AccessTokenClaims, order_id: str) -> dict[str, Any]:
        scope = ScopeResolver.resolve_from_claims(claims, OrgResource.ACTIVITY_DATA)
        order = repository.get_order_in_scope(self._session, scope=scope, order_id=order_id)
        if order is None:
            raise ApiError(404, "order_not_found", "Order was not found.")
        return self._order_payload(order, include_lines=True)

    def order_ids_by_visit(self, *, tenant_id: str, visit_ids: list[str]) -> dict[str, list[str]]:
        return repository.order_ids_by_visit(self._session, tenant_id=tenant_id, visit_ids=visit_ids)

    def _order_summary(self, order: Order) -> schemas.OrderSummaryOut:
        return schemas.OrderSummaryOut(
            id=order.id, order_number=order.order_number,
            order_path=cast(schemas.OrderPath, order.order_path), status=order.status,
            outlet_name=order.outlet_name_snapshot, counterparty_name=order.seller_name_snapshot,
            gross_total_paise=(
                order.approved_gross_total_paise
                if order.approved_gross_total_paise is not None
                else order.gross_total_paise
            ),
            business_date=order.business_date,
            downstream_dp_order_ref=order.downstream_dp_order_ref,
        )

    def _order_payload(self, order: Order, *, include_lines: bool) -> dict[str, Any]:
        summary = self._order_summary(order)
        lines = repository.list_order_lines(self._session, order_id=order.id) if include_lines else []
        subtotal_net_paise = (
            order.approved_subtotal_net_paise
            if order.approved_subtotal_net_paise is not None
            else order.subtotal_net_paise
        )
        scheme_discount_paise = min(order.scheme_discount_paise, subtotal_net_paise)
        product_discount_paise = min(
            order.product_discount_paise, subtotal_net_paise - scheme_discount_paise
        )
        gst_amount_paise = (
            sum(
                (
                    line.approved_line_gst_amount_paise
                    if line.approved_line_gst_amount_paise is not None
                    else line.line_gst_amount_paise
                )
                for line in lines
            )
            if include_lines
            else order.gst_amount_paise
        )
        taxable_base_paise = max(summary.gross_total_paise - gst_amount_paise, 0)
        return schemas.OrderDetailOut(
            **summary.model_dump(),
            lines=[
                schemas.OrderLineOut(
                    line_no=line.line_no,
                    product_id=line.humbee_product_id,
                    product_name=line.product_name_snapshot,
                    pack_size=line.pack_size_snapshot or line.uom_snapshot,
                    form_type=cast(Any, line.form_type),
                    unit_price_net_paise=line.unit_price_net_paise,
                    requested_qty=line.requested_qty,
                    approved_qty=(
                        line.approved_qty if line.approved_qty is not None else line.requested_qty
                    ),
                    line_net_paise=line.line_net_paise,
                    approved_line_net_paise=(
                        line.approved_line_net_paise
                        if line.approved_line_net_paise is not None
                        else line.line_net_paise
                    ),
                    line_gst_amount_paise=line.line_gst_amount_paise,
                    scheme_line_discount_paise=line.scheme_line_discount_paise,
                    product_line_discount_paise=line.product_line_discount_paise,
                    approved_line_gst_amount_paise=(
                        line.approved_line_gst_amount_paise
                        if line.approved_line_gst_amount_paise is not None
                        else line.line_gst_amount_paise
                    ),
                )
                for line in lines
            ],
            subtotal_net_paise=subtotal_net_paise,
            scheme_discount_paise=scheme_discount_paise,
            scheme_label=order.scheme_label_snapshot,
            product_discount_paise=product_discount_paise,
            taxable_base_paise=taxable_base_paise,
            gst_amount_paise=gst_amount_paise,
            requires_approval=order.requires_approval, approver_name=order.approver_name_snapshot,
            sub_status_reason=order.sub_status_reason, dp_sla_deadline_at=order.dp_sla_deadline_at,
            retry_budget_remaining=order.retry_budget_remaining, submitted_at=order.created_at,
            approved_at=order.approved_at,
        ).model_dump(mode="json")
