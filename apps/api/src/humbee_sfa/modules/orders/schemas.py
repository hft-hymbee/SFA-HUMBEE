"""Orders/cart HTTP DTOs (M10 §3.3, §4 S-ORD1-4; epic 07 Stories 7.4-7.6)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OrderPath = Literal["po_backed", "direct"]
ShipToType = Literal["self", "dealer"]
FormType = Literal["STRAIGHT", "BEND"]


class CreateCartBody(BaseModel):
    visit_id: str = Field(min_length=1, max_length=26)
    outlet_id: str = Field(min_length=1, max_length=64)
    manufacturer_id: str = Field(
        min_length=1,
        max_length=64,
        description="Humbee brand_id selected from the outlet sellers response; sent upstream as manufacturer_id.",
    )
    # Required only when the outlet has more than one active seller linked for the brand
    # — `get_order_context` lists the choices when disambiguation is needed.
    seller_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional; pass only when order context returns seller_selection_required.",
    )


class ShippingAddressOverride(BaseModel):
    line1: str = Field(min_length=1, max_length=250)
    line2: str | None = Field(default=None, max_length=250)
    state_id: str = Field(min_length=1, max_length=64)
    district_id: str = Field(min_length=1, max_length=64)
    # Required alongside district_id: Humbee's `requested_district_id`/`requested_pincode` are
    # sent as a pair or not at all (SFAShipToPartyInfoApiDTO).
    pincode: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PatchCartBody(BaseModel):
    source_po_id: str | None = None
    outlet_esi_id: str | None = None
    seller_esi_id: str | None = None
    ship_to_type: ShipToType | None = None
    ship_to_outlet_id: str | None = None
    ship_to_esi_id: str | None = None
    shipping_address_override: ShippingAddressOverride | None = None


class UpsertLineBody(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    qty: int = Field(ge=0)
    form_type: FormType | None = None


class UpsertLinesBody(BaseModel):
    lines: list[UpsertLineBody] = Field(min_length=1)


class CartLineOut(BaseModel):
    product_id: str
    qty: int
    form_type: FormType | None
    unit_price_net_paise: int | None
    unit_price_as_of: datetime
    line_net_paise: int
    line_gst_amount_paise: int
    price_changed: bool


class CartResponse(BaseModel):
    id: str
    status: str
    visit_id: str | None
    outlet_id: str
    manufacturer_id: str
    seller_id: str
    outlet_esi_id: str | None
    seller_esi_id: str | None
    seller_name: str
    order_path: OrderPath
    seller_type_snapshot: str
    source_po_id: str | None
    ship_to_type: str | None
    ship_to_outlet_id: str | None
    ship_to_esi_id: str | None
    shipping_address_override: ShippingAddressOverride | None
    lines: list[CartLineOut]
    subtotal_net_paise: int
    scheme_discount_paise: int
    scheme_label: str | None
    product_discount_paise: int
    taxable_base_paise: int
    gst_amount_paise: int
    gross_total_paise: int
    # epic 07 Story 7.5 PO caps: `po_cap_qty` is `min(max_dp_quantity, available_quantity)`,
    # `po_cap_source` names whichever of the two bound it. Both null off the PO-backed path or
    # when no PO is selected yet.
    po_cap_qty: int | None
    po_cap_source: Literal["max_dp_quantity", "available_quantity"] | None
    # per-product remaining PO quantity (P-2 `lines[].balance_qty`), keyed by product_id; only
    # products the PO carries a line for are present, so a missing key means no per-SKU cap.
    po_line_balances: dict[str, int]
    expires_at: datetime
    as_of: datetime


class PurchaseOrderOut(BaseModel):
    po_id: str
    po_number: str
    status: str
    manufacturer_id: str
    manufacturer_name: str
    net_value_paise: int
    balance_value_paise: int
    max_dp_quantity: int | None
    available_quantity: int | None
    po_date: date
    valid_until: date | None


class ShipToOptionOut(BaseModel):
    party_id: str
    esi_id: str
    # The external/SAP code — shown to the user for reconciliation, never sent back on a write.
    esi_code: str | None
    name: str
    address_line1: str
    address_line2: str | None
    address_line3: str | None
    state_id: str | None
    district_id: str | None
    pincode: str | None
    geographic_info: dict[str, Any] | None = None
    is_self: bool


class ServiceableStateOut(BaseModel):
    state_id: str
    state_name: str


class ServiceableStatesResponse(BaseModel):
    states: list[ServiceableStateOut]


class ServiceableDistrictOut(BaseModel):
    district_id: str
    district_name: str


class ServiceableDistrictsResponse(BaseModel):
    districts: list[ServiceableDistrictOut]


class SellerOut(BaseModel):
    seller_id: str
    seller_type: str
    name: str
    address: str | None = None
    requires_purchase_order: bool
    manager_approval_required: bool


class OrderContextResponse(BaseModel):
    """S-ORD1 fan-out. `no_sellers_linked` and `seller_selection_required`
    are first-class recovery states, not errors — when either is true the routing/PO/ship-to/
    banner fields are empty and the client renders the recovery screen instead."""

    outlet_id: str
    manufacturer_id: str
    manufacturer_name: str
    sellers: list[SellerOut]
    sellers_filtered_by_district: bool
    no_sellers_linked: bool
    seller_selection_required: bool
    selected_seller_id: str | None
    order_path: OrderPath | None
    requires_approval: bool | None
    purchase_orders: list[PurchaseOrderOut]
    default_source_po_id: str | None
    ship_to_options: list[ShipToOptionOut]
    delivery_available: bool
    delivery_block_reason: str | None
    banner: str | None
    as_of: datetime


class PurchaseOrdersResponse(BaseModel):
    purchase_orders: list[PurchaseOrderOut]
    as_of: datetime


class CatalogProductOut(BaseModel):
    product_id: str
    name: str
    image_url: str | None
    category: str | None
    category_id: str | None
    category_name: str | None
    pack_size: str | None
    uom: str
    multiplier: int
    unit_price_net_paise: int | None
    discount_rate_bp: int
    gst_rate_bp: int
    stock_status: str | None
    form_type_req: bool
    qty_in_cart: int


class CatalogResponse(BaseModel):
    products: list[CatalogProductOut]
    cart_item_count: int
    cart_subtotal_net_paise: int
    as_of: datetime


# -- order submission / read (Story 4.2/4.3; epic 07 Story 7.6) -------------


class SubmitOrderBody(BaseModel):
    cart_id: str = Field(min_length=1, max_length=26)
    occurred_at: datetime | None = None


class OrderLineOut(BaseModel):
    line_no: int
    product_id: str
    product_name: str
    pack_size: str | None
    form_type: FormType | None
    unit_price_net_paise: int | None
    requested_qty: int
    approved_qty: int | None
    line_net_paise: int
    line_gst_amount_paise: int
    scheme_line_discount_paise: int
    product_line_discount_paise: int
    approved_line_net_paise: int | None
    approved_line_gst_amount_paise: int | None


class OrderSummaryOut(BaseModel):
    id: str
    order_number: str
    order_path: OrderPath
    status: str
    outlet_name: str
    counterparty_name: str
    gross_total_paise: int
    business_date: date
    downstream_dp_order_ref: str | None


class OrderDetailOut(OrderSummaryOut):
    lines: list[OrderLineOut]
    subtotal_net_paise: int
    scheme_discount_paise: int
    scheme_label: str | None = None
    product_discount_paise: int = 0
    taxable_base_paise: int
    gst_amount_paise: int
    requires_approval: bool
    approver_name: str | None
    sub_status_reason: str | None
    dp_sla_deadline_at: datetime | None
    retry_budget_remaining: int
    submitted_at: datetime
    approved_at: datetime | None


class OrderListResponse(BaseModel):
    items: list[OrderSummaryOut]
    next_cursor: str | None
