"""Provider-neutral port for Humbee commerce reads and the order-registration write.

Routing (PO-backed vs direct, approval-required or not) is decided entirely from a `SellerRecord`
chosen for the outlet+brand — this port carries no outlet classification/tier concept.

Price and stock are fields on `ProductRecord` — there is no separate price or stock endpoint.
`unit_price_net_paise`/`stock_status` are nullable and mean unverified/unknown, never zero or
"out of stock".

Reconciled against the live OpenAPI document and live calls against `api-dev.humbee.in` on
2026-08-30. Almost every capability here is keyed on an **ESI id**, not a firm id; `outlet_id` and
`manufacturer_id` alone are not enough to resolve pricing, stock, ship-to or order routing.

`GET /sfa/v1/manufacturers/{id}` does not exist — only the outlet-scoped list
(`GET /sfa/v1/manufacturers?outlet_id=...`, response `{manufacturers: [{manufacturer_id,
manufacturer_name, brands[], products[]}], as_of}`) — `get_partner` matches client-side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

import structlog

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import (
    HumbeeError,
    HumbeeTransportError,
    get_humbee_client,
)


@dataclass(frozen=True)
class PartnerRecord:
    external_id: str
    name: str


@dataclass(frozen=True)
class ShipToOption:
    """One deliverable (party, ESI) combination — a genuinely distinct destination (a separate
    internal shop or registration), not a duplicate to collapse. A party with more than one
    operational address appears once per ESI. `esi_id` is sent as `deliver_to_esi_id`, `party_id`
    as `deliver_to`, on order registration. `esi_code` is the external/SAP code — shown to the
    user for reconciliation, never sent on a write; Humbee holds the SAP mapping against `esi_id`
    itself."""

    party_id: str
    esi_id: str
    esi_code: str | None
    name: str
    address_line1: str
    address_line2: str | None
    address_line3: str | None
    state_id: str | None
    district_id: str | None
    pincode: str | None
    geographic_info: dict[str, Any]
    is_self: bool


@dataclass(frozen=True)
class ServiceableState:
    external_id: str
    name: str


@dataclass(frozen=True)
class ServiceableDistrict:
    external_id: str
    name: str


@dataclass(frozen=True)
class PurchaseOrderLineRecord:
    """One PO line (the purchase-order `lines[]`). Never cached —
    `balance_qty` is as volatile as the header totals. Inactive lines are excluded by
    `_parse_po_line` filtering at the call site, not carried as a flag here."""

    product_id: str
    balance_qty: int


@dataclass(frozen=True)
class PurchaseOrderRecord:
    """Never cached — `balance_value_paise` is the most volatile figure in the flow.
    `max_dp_quantity`/`available_quantity` back the cart-level cap (`min` of the two). `lines`
    backs the per-SKU cap (`balance_qty`) — SKU choices themselves still come from the product API
    after a PO is selected."""

    external_id: str
    number: str
    status: str
    manufacturer_id: str
    manufacturer_name: str
    net_value_paise: int
    balance_value_paise: int
    max_dp_quantity: int | None
    available_quantity: int | None
    po_date: date
    valid_until: date | None
    payment_terms: str | None
    credit_days: int | None
    lines: tuple[PurchaseOrderLineRecord, ...]
    as_of: datetime


@dataclass(frozen=True)
class ProductRecord:
    """Catalogue row, outlet-priced. `multiplier` is per product, never a fixed constant.
    `unit_price_net_paise`/`stock_status` are `None` when Humbee hasn't populated them — never
    defaulted. `pack_size`/`hsn_code` dropped from the response on 26 Aug 2026 and are `None`
    rather than a fabricated placeholder; `manufacturer_id` and `is_active` were dropped from the
    same response and are gone from this record entirely — the caller already knows
    `manufacturer_id`, and stock_status (never a hard block, see `register_order`) replaced any
    active/inactive concept."""

    external_id: str
    name: str
    image_url: str | None
    category_id: str | None
    category_name: str | None
    pack_size: str | None
    uom: str
    hsn_code: str | None
    gst_rate_bp: int
    discount_rate_bp: int
    multiplier: int
    unit_price_net_paise: int | None
    stock_status: str | None  # 'in_stock' | 'low_stock' | 'out_of_stock' | None (unknown)
    form_type_req: bool


@dataclass(frozen=True)
class SchemeEvaluation:
    label: str | None
    discount_paise: int


@dataclass(frozen=True)
class RegisterOrderLine:
    product_id: str
    quantity_in_uom: int
    bundle: int
    remark: str
    form_type: Literal["STRAIGHT", "BEND"] | None = None


@dataclass(frozen=True)
class RegisterOrderResult:
    """`accepted_gross_total_paise` backs the reconciliation-against-approved-total check; `None`
    when there's nothing comparable on either side, which must degrade to "not checked", never
    crash or guess."""

    dp_order_ref: str
    accepted_gross_total_paise: int | None


class CommerceUnavailable(RuntimeError):
    pass


class SchemeUnavailable(RuntimeError):
    pass


class ServiceableGeographyUnavailable(RuntimeError):
    pass


class OrderRegistrationFailed(RuntimeError):
    def __init__(self, message: str, *, failure_class: str = "failed_terminal") -> None:
        super().__init__(message)
        self.failure_class = failure_class


logger = structlog.get_logger("humbee_sfa.integration.humbee.commerce")

_PRODUCTS_PAGE_SIZE = 100
_OPEN_PO_STATUSES = frozenset({"APPROVED", "PARTIALLY_COMPLETED", "OPEN"})
_HUMBEE_FORM_TYPE = {"STRAIGHT": 1, "BEND": 2}
_FAILURE_CLASS_BY_ERROR_CODE = {
    "030": "outlet_inactive",
    "998": "validation_rejected",
    # whether the order landed is genuinely unknown on 999, same ambiguity as a timeout
    "999": "timeout",
}


def _as_of(raw: str | None) -> datetime:
    return datetime.fromisoformat(raw) if raw else datetime.now(UTC)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_csv_token(value: Any) -> str | None:
    text = _text_or_none(value)
    if text is None:
        return None
    first_token = text.split(",", 1)[0].strip()
    return first_token or None


def _parse_product(entry: dict[str, Any]) -> ProductRecord | None:
    product_id = entry.get("product_id") or entry.get("id")
    if product_id is None:
        logger.warning("humbee_product_field_missing", capability="commerce.products")
        return None
    category_id = entry.get("category_id")
    category_name = entry.get("category_name") or entry.get("category")
    return ProductRecord(
        external_id=str(product_id),
        name=str(entry.get("name") or ""),
        image_url=_first_csv_token(entry.get("product_url")),
        category_id=str(category_id) if category_id is not None else None,
        category_name=str(category_name) if category_name is not None else None,
        pack_size=entry.get("pack_size"),
        uom=str(entry.get("uom") or "EA"),
        hsn_code=entry.get("hsn_code"),
        gst_rate_bp=int(entry.get("gst_rate_bp") or 0),
        discount_rate_bp=int(entry.get("discount_rate_bp") or 0),
        multiplier=int(entry.get("multiplier") or 1),
        unit_price_net_paise=entry.get("unit_price_net_paise"),
        stock_status=entry.get("stock_status"),
        form_type_req=bool(entry.get("form_type_req")),
    )


def _parse_po_line(entry: dict[str, Any]) -> PurchaseOrderLineRecord | None:
    product_id = entry.get("product_id")
    if product_id is None:
        logger.warning("humbee_po_line_field_missing", capability="commerce.purchase_orders")
        return None
    return PurchaseOrderLineRecord(
        product_id=str(product_id),
        balance_qty=int(entry.get("balance_qty") or 0),
    )


def _parse_po(entry: dict[str, Any]) -> PurchaseOrderRecord:
    as_of = _as_of(entry.get("as_of"))
    valid_until = entry.get("valid_until")
    po_date = entry.get("po_date")
    return PurchaseOrderRecord(
        external_id=str(entry.get("po_id") or entry.get("id")),
        number=str(entry.get("number") or entry.get("po_number") or ""),
        status=str(entry.get("status") or ""),
        manufacturer_id=str(entry.get("manufacturer_id") or ""),
        manufacturer_name=str(entry.get("manufacturer_name") or ""),
        net_value_paise=int(entry.get("net_value_paise") or entry.get("po_net_value_paise") or 0),
        balance_value_paise=int(entry.get("balance_value_paise") or 0),
        max_dp_quantity=_int_or_none(entry.get("max_dp_quantity")),
        available_quantity=_int_or_none(entry.get("available_quantity")),
        po_date=datetime.fromisoformat(po_date).date() if po_date else as_of.date(),
        valid_until=datetime.fromisoformat(valid_until).date() if valid_until else None,
        payment_terms=entry.get("payment_terms"),
        credit_days=entry.get("credit_days"),
        lines=tuple(
            line for e in entry.get("lines") or ()
            if e.get("is_active", True) and (line := _parse_po_line(e)) is not None
        ),
        as_of=as_of,
    )


def _partner_from_entry(entry: dict[str, Any], partner_id: str) -> PartnerRecord | None:
    if str(entry.get("manufacturer_id")) == partner_id:
        return PartnerRecord(
            external_id=partner_id,
            name=str(entry.get("manufacturer_name") or ""),
        )
    for brand in entry.get("brands") or ():
        if str(brand.get("brand_id")) == partner_id:
            name = brand.get("brand_name") or brand.get("name") or brand.get("brand")
            return PartnerRecord(external_id=partner_id, name=str(name or ""))
    return None


class HumbeeCommerceProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def get_partner(self, *, tenant_id: str, outlet_id: str, partner_id: str) -> PartnerRecord:
        del tenant_id
        try:
            data = self._client.call(
                "commerce.manufacturers", "GET", "/sfa/v1/manufacturers",
                params={"outlet_id": outlet_id},
            )
        except HumbeeError as exc:
            raise CommerceUnavailable(str(exc)) from exc
        try:
            for entry in data.get("manufacturers") or ():
                if partner := _partner_from_entry(entry, partner_id):
                    return partner
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CommerceUnavailable(
                f"unexpected manufacturers response shape: {exc}"
            ) from exc
        raise CommerceUnavailable(f"manufacturer {partner_id} not linked to outlet {outlet_id}")

    def list_ship_to_options(
        self, *, tenant_id: str, outlet_id: str, buyer_esi_id: str
    ) -> list[ShipToOption]:
        del tenant_id, outlet_id
        try:
            data = self._client.call(
                "commerce.ship_to", "GET", "/sfa/v1/sellers/ship-to-options",
                params={"outlet_esi_id": buyer_esi_id},
            )
        except HumbeeError as exc:
            raise CommerceUnavailable(str(exc)) from exc
        options: list[ShipToOption] = []
        try:
            for entry in data.get("ship_to_options") or ():
                party_id = entry.get("ship_to_party_id")
                if party_id is None:
                    continue
                is_self = bool(entry.get("is_self"))
                name = str(entry.get("name") or "")
                geographic_info: dict[str, Any] = entry["geographic_info"]
                for esi_entry in entry.get("esi_info_with_operational_address") or ():
                    esi_info = esi_entry.get("esi_info") or {}
                    esi_id = esi_info.get("esi_id")
                    if esi_id is None:
                        continue
                    esi_code = esi_info.get("esi_code")
                    address = esi_entry.get("address") or {}
                    address_info = address.get("address_info") or {}
                    state_info = address.get("state_info") or {}
                    district_info = address.get("district_info") or {}
                    pincode_info = address.get("pincode_info") or {}
                    geographic_state = (geographic_info.get("state_info") or {}).get("state_id")
                    geographic_district = (geographic_info.get("district_info") or {}).get("district_id")
                    geographic_pincode = (geographic_info.get("pincode_info") or {}).get("pincode_id")
                    options.append(
                        ShipToOption(
                            party_id=str(party_id),
                            esi_id=str(esi_id),
                            esi_code=str(esi_code) if esi_code is not None else None,
                            name=name,
                            address_line1=str(address_info.get("address_line_1") or ""),
                            address_line2=_text_or_none(address_info.get("address_line_2")),
                            address_line3=_text_or_none(address_info.get("address_line_3")),
                            state_id=(
                                _text_or_none(state_info.get("state_id"))
                                or _text_or_none(geographic_state)
                            ),
                            district_id=(
                                _text_or_none(district_info.get("district_id"))
                                or _text_or_none(geographic_district)
                            ),
                            pincode=(
                                _text_or_none(pincode_info.get("pincode_id"))
                                or _text_or_none(pincode_info.get("pincode_name"))
                                or _text_or_none(pincode_info.get("pincode"))
                                or _text_or_none(geographic_pincode)
                            ),
                            geographic_info=geographic_info,
                            is_self=is_self,
                        )
                    )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CommerceUnavailable(f"unexpected ship-to response shape: {exc}") from exc
        return options

    def list_open_purchase_orders(
        self,
        *,
        tenant_id: str,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str | None,
    ) -> list[PurchaseOrderRecord]:
        del tenant_id
        params: dict[str, Any] = {"outlet_id": outlet_id, "manufacturer_id": manufacturer_id}
        if outlet_esi_id:
            params["outlet_esi_id"] = outlet_esi_id
        try:
            data = self._client.call(
                "commerce.purchase_orders", "GET", "/sfa/v1/purchase-orders", params=params
            )
        except HumbeeError as exc:
            raise CommerceUnavailable(str(exc)) from exc
        # status filtering is client-side — the endpoint returns every PO, open or not
        return [
            po for entry in data.get("purchase_orders") or ()
            if (po := _parse_po(entry)).status.upper() in _OPEN_PO_STATUSES
        ]

    def list_products(
        self,
        *,
        tenant_id: str,
        outlet_id: str,
        manufacturer_id: str,
        outlet_esi_id: str | None,
        seller_esi_id: str | None,
        district_id: str | None,
        po_id: str | None,
        category: str | None,
        query: str | None,
    ) -> list[ProductRecord]:
        del tenant_id
        params: dict[str, Any] = {
            "manufacturer_id": manufacturer_id, "outlet_id": outlet_id, "limit": _PRODUCTS_PAGE_SIZE,
        }
        if outlet_esi_id:
            params["outlet_esi_id"] = outlet_esi_id
        if seller_esi_id:
            params["seller_esi_id"] = seller_esi_id
        if district_id:
            params["district_id"] = district_id
        if po_id:
            params["po_id"] = po_id
        if category:
            params["category_id"] = category
        trimmed_query = (query or "").strip()
        if trimmed_query:
            params["query"] = trimmed_query

        products: list[ProductRecord] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page_params = dict(params)
            if cursor:
                page_params["cursor"] = cursor
            try:
                data = self._client.call("commerce.products", "GET", "/sfa/v1/products", params=page_params)
            except HumbeeError as exc:
                raise CommerceUnavailable(str(exc)) from exc
            products.extend(
                product for entry in data.get("products") or ()
                if (product := _parse_product(entry)) is not None
            )
            cursor = data.get("next_cursor")
            if not cursor:
                return products
            if cursor in seen_cursors:
                raise CommerceUnavailable("products pagination did not advance")
            seen_cursors.add(cursor)

    def list_serviceable_states(
        self, *, tenant_id: str, manufacturer_id: str
    ) -> list[ServiceableState]:
        """`GET /sfa/v1/states` with `manufacturer_id` — every state this manufacturer delivers to,
        for the shipping-address state dropdown. The same endpoint answers a different question
        without `manufacturer_id` — where a firm may be addressed at all — and that reading lives in
        `onboarding.py`; the two stay apart because their failures differ (an address form degrades
        to manual entry, an unanswerable serviceability check blocks an order)."""

        del tenant_id
        try:
            data = self._client.call(
                "commerce.states", "GET", "/sfa/v1/states",
                params={"manufacturer_id": manufacturer_id},
            )
        except HumbeeError as exc:
            raise ServiceableGeographyUnavailable(str(exc)) from exc
        try:
            return [
                ServiceableState(
                    external_id=str(state["state_id"]), name=str(state.get("state_name") or "")
                )
                for state in data["states"]
            ]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ServiceableGeographyUnavailable(
                f"unexpected serviceable states response shape: {exc}"
            ) from exc

    def list_serviceable_districts(
        self, *, tenant_id: str, manufacturer_id: str, state_id: str
    ) -> list[ServiceableDistrict]:
        """The districts, within one state, this manufacturer delivers to.

        `state_id` is required upstream and bounds the answer; there is no national district
        listing, so this can only be asked one state at a time — the UI supplies it from whichever
        state the person picked from `list_serviceable_states` first.
        """

        del tenant_id
        try:
            data = self._client.call(
                "commerce.districts", "GET", "/sfa/v1/districts",
                params={"state_id": state_id, "manufacturer_id": manufacturer_id},
            )
        except HumbeeError as exc:
            raise ServiceableGeographyUnavailable(str(exc)) from exc
        try:
            return [
                ServiceableDistrict(
                    external_id=str(district["district_id"]),
                    name=str(district.get("district_name") or ""),
                )
                for district in data["districts"]
            ]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ServiceableGeographyUnavailable(
                f"unexpected serviceable districts response shape: {exc}"
            ) from exc

    def is_district_serviceable(
        self, *, tenant_id: str, manufacturer_id: str, state_id: str, district_id: str
    ) -> bool:
        """Matching is by id, never by name: district names are not unique across states —
        PRATAPGARH exists in both Uttar Pradesh and Rajasthan. Same upstream call as
        `list_serviceable_districts` — this is a membership check over it, not a second one."""

        return any(
            district.external_id == district_id
            for district in self.list_serviceable_districts(
                tenant_id=tenant_id, manufacturer_id=manufacturer_id, state_id=state_id
            )
        )

    def evaluate_scheme(
        self,
        *,
        tenant_id: str,
        outlet_id: str,
        manufacturer_id: str,
        lines: list[tuple[str, int]],
    ) -> SchemeEvaluation:
        del tenant_id
        if not lines:
            return SchemeEvaluation(label=None, discount_paise=0)
        body = {
            "outlet_id": outlet_id,
            "lines": [
                {"product_id": product_id, "qty": qty}
                for product_id, qty in lines
            ],
        }
        try:
            data = self._client.call(
                "commerce.schemes.evaluate",
                "POST",
                "/sfa/v1/schemes/evaluate",
                params={"manufacturer_id": manufacturer_id},
                json_body=body,
                max_retries=0,
            )
        except (AttributeError, KeyError, TypeError, ValueError, HumbeeError) as exc:
            raise SchemeUnavailable(str(exc)) from exc
        return SchemeEvaluation(
            label=_text_or_none(data.get("scheme_label")),
            discount_paise=int(data.get("discount_paise") or 0),
        )

    def register_order(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        outlet_id: str,
        manufacturer_id: str,
        buyer_esi_id: str | None,
        seller_id: str,
        seller_esi_id: str | None,
        source_po_id: str | None,
        ship_to_outlet_id: str | None,
        ship_to_esi_id: str | None,
        requested_district_id: str | None,
        requested_pincode: str | None,
        lines: list[RegisterOrderLine],
        source: str,
        sfa_order_reference: str,
        placed_by: str,
        approved_by: str | None,
        occurred_at: datetime,
    ) -> RegisterOrderResult:
        del tenant_id
        if not buyer_esi_id:
            raise OrderRegistrationFailed(
                "Missing buyer ESI id for order registration.",
                failure_class="failed_terminal",
            )
        deliver_to = ship_to_outlet_id or outlet_id
        deliver_to_esi_id = ship_to_esi_id or buyer_esi_id
        ship_to_party_info: dict[str, Any] = {
            "deliver_to": deliver_to,
            "deliver_to_esi_id": deliver_to_esi_id,
            "order_product_delivery_type": 1,  # SFA only ever ships physically
        }
        # SFAShipToPartyInfoApiDTO: sent as a pair or not at all.
        if requested_district_id and requested_pincode:
            ship_to_party_info["requested_district_id"] = requested_district_id
            ship_to_party_info["requested_pincode"] = requested_pincode
        body: dict[str, Any] = {
            "buyer_id": outlet_id,
            "buyer_esi_id": buyer_esi_id,
            "seller_id": seller_id,
            "supplier_id": manufacturer_id,
            "order_products_delivery": [
                {
                    "ship_to_party_info": ship_to_party_info,
                    "products_info": [
                        {
                            "product_id": line.product_id,
                            "quantity": {
                                "quantity_in_uom": line.quantity_in_uom,
                            },
                            "bundle": line.bundle,
                            "remark": line.remark,
                            **(
                                {"form_type": _HUMBEE_FORM_TYPE[line.form_type]}
                                if line.form_type in _HUMBEE_FORM_TYPE
                                else {}
                            ),
                        }
                        for line in lines
                    ],
                }
            ],
            "source": source,
            "sfa_order_reference": sfa_order_reference,
            "placed_by": placed_by,
            "occurred_at": occurred_at.isoformat(),
        }
        if source_po_id:
            body["order_booking_id"] = source_po_id
        if seller_esi_id:
            body["seller_esi_id"] = seller_esi_id
        if approved_by:
            body["approved_by"] = approved_by
        try:
            data = self._client.call(
                "commerce.register_order", "POST", "/sfa/v1/orders",
                params={"manufacturer_id": manufacturer_id}, json_body=body,
                idempotency_key=idempotency_key,
                # 1 retry (2 attempts total), jittered exponential backoff (client.py).
                max_retries=1,
            )
        except HumbeeTransportError as exc:
            # a timeout/network failure never proves the write didn't land — ambiguous, not failed
            raise OrderRegistrationFailed(str(exc), failure_class="timeout") from exc
        except HumbeeError as exc:
            failure_class = _FAILURE_CLASS_BY_ERROR_CODE.get(exc.error_code or "", "failed_terminal")
            raise OrderRegistrationFailed(str(exc), failure_class=failure_class) from exc
        # We persist this as a downstream identity and guard it with a unique index, so blank/whitespace
        # refs are not valid and must be treated as an ambiguous outcome that needs reconciliation.
        dp_order_ref = (
            _text_or_none(data.get("dp_order_ref"))
            or _text_or_none(data.get("dp_order_number"))
            or _text_or_none(data.get("dp_order_id"))
            or _text_or_none(data.get("order_id"))
        )
        if dp_order_ref is None:
            raise OrderRegistrationFailed(
                "Order registration response did not include a downstream order reference.",
                failure_class="timeout",
            )

        return RegisterOrderResult(
            dp_order_ref=dp_order_ref,
            accepted_gross_total_paise=data.get("accepted_gross_total_paise"),
        )
