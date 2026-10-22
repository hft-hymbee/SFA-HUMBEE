from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

import httpx
from tests.fakes.humbee import AS_OF, FakeHumbee, HumbeeCall


@dataclass
class Product:
    product_id: str
    name: str
    unit_price_net_paise: int | None
    gst_rate_bp: int
    discount_rate_bp: int = 0
    manufacturer_id: str = "MFR-1"
    uom: str = "EA"
    stock_status: str | None = "in_stock"
    form_type_req: bool = False


@dataclass
class Seller:
    seller_id: str
    name: str
    seller_type: str = "R1"
    is_active: bool = True
    requires_purchase_order: bool = False
    manager_approval_required: bool = False
    outlet_esi_ids: tuple[str, ...] = ("ESI-OUT-1",)
    seller_esi_ids: tuple[str, ...] = ("ESI-SEL-1",)


@dataclass
class PurchaseOrder:
    po_id: str
    manufacturer_id: str = "MFR-1"
    status: str = "OPEN"
    max_dp_quantity: int | None = None
    available_quantity: int | None = None
    line_balances: dict[str, int] = field(default_factory=dict)


@dataclass
class ShipTo:
    party_id: str
    esi_id: str
    name: str
    state_id: str = "10"
    district_id: str = "100"
    is_self: bool = False


@dataclass
class FakeCommerce:
    manufacturers: dict[str, str] = field(default_factory=dict)
    sellers: dict[tuple[str, str], list[Seller]] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    purchase_orders: list[PurchaseOrder] = field(default_factory=list)
    ship_to: list[ShipTo] = field(default_factory=list)
    scheme_discount_paise: int = 0
    scheme_label: str | None = None
    registration_timeouts: int = 0
    _dp_numbers: itertools.count[int] = field(default_factory=lambda: itertools.count(1))

    def add_manufacturer(self, manufacturer_id: str, name: str) -> None:
        self.manufacturers[manufacturer_id] = name

    def link_seller(self, outlet_id: str, manufacturer_id: str, seller: Seller) -> Seller:
        self.sellers.setdefault((outlet_id, manufacturer_id), []).append(seller)
        return seller

    def add_product(self, product: Product) -> Product:
        self.products[product.product_id] = product
        return product

    def _outlet_sellers(self, call: HumbeeCall) -> Any:
        outlet_id = call.path_params["outlet_id"]
        groups = [
            {
                "brand_id": manufacturer_id,
                "brand_name": self.manufacturers.get(manufacturer_id, manufacturer_id),
                "sellers_filtered_by_district": True,
                "sellers": [
                    {
                        "seller_id": s.seller_id,
                        "seller_type": s.seller_type,
                        "name": s.name,
                        "is_active": s.is_active,
                        "requires_purchase_order": s.requires_purchase_order,
                        "manager_approval_required": s.manager_approval_required,
                        "seller_esi_records": [{"esi_id": e, "esi_code": f"C-{e}"} for e in s.seller_esi_ids],
                        "outlet_esi_records": [{"esi_id": e, "esi_code": f"C-{e}"} for e in s.outlet_esi_ids],
                    }
                    for s in sellers
                ],
            }
            for (owner, manufacturer_id), sellers in self.sellers.items()
            if owner == outlet_id
        ]
        return {"sellers_by_brand": groups, "as_of": AS_OF}

    def _manufacturers(self, call: HumbeeCall) -> Any:
        outlet_id = call.params["outlet_id"]
        linked = {manufacturer_id for owner, manufacturer_id in self.sellers if owner == outlet_id}
        return {
            "manufacturers": [
                {"manufacturer_id": m, "manufacturer_name": name, "brands": [], "products": []}
                for m, name in self.manufacturers.items()
                if m in linked
            ],
            "as_of": AS_OF,
        }

    def _products(self, call: HumbeeCall) -> Any:
        manufacturer_id = call.params["manufacturer_id"]
        return {
            "products": [
                {
                    "product_id": p.product_id,
                    "name": p.name,
                    "category_id": "CAT-1",
                    "category_name": "Cement",
                    "uom": p.uom,
                    "gst_rate_bp": p.gst_rate_bp,
                    "discount_rate_bp": p.discount_rate_bp,
                    "multiplier": 1,
                    "unit_price_net_paise": p.unit_price_net_paise,
                    "stock_status": p.stock_status,
                    "form_type_req": p.form_type_req,
                }
                for p in self.products.values()
                if p.manufacturer_id == manufacturer_id
            ],
            "next_cursor": None,
        }

    def _evaluate_scheme(self, call: HumbeeCall) -> Any:
        return {"scheme_label": self.scheme_label, "discount_paise": self.scheme_discount_paise}

    def _purchase_orders(self, call: HumbeeCall) -> Any:
        manufacturer_id = call.params["manufacturer_id"]
        return {
            "purchase_orders": [
                {
                    "po_id": po.po_id,
                    "number": f"N-{po.po_id}",
                    "status": po.status,
                    "manufacturer_id": po.manufacturer_id,
                    "manufacturer_name": self.manufacturers.get(po.manufacturer_id, ""),
                    "net_value_paise": 10_000_000,
                    "balance_value_paise": 5_000_000,
                    "max_dp_quantity": po.max_dp_quantity,
                    "available_quantity": po.available_quantity,
                    "po_date": "2026-10-01",
                    "valid_until": "2026-12-31",
                    "lines": [{"product_id": pid, "balance_qty": qty} for pid, qty in po.line_balances.items()],
                    "as_of": AS_OF,
                }
                for po in self.purchase_orders
                if po.manufacturer_id == manufacturer_id
            ],
            "as_of": AS_OF,
        }

    def _ship_to_options(self, call: HumbeeCall) -> Any:
        return {
            "ship_to_options": [
                {
                    "ship_to_party_id": option.party_id,
                    "name": option.name,
                    "is_self": option.is_self,
                    "geographic_info": {
                        "state_info": {"state_id": option.state_id},
                        "district_info": {"district_id": option.district_id},
                        "pincode_info": {"pincode_id": "560001"},
                    },
                    "esi_info_with_operational_address": [
                        {
                            "esi_info": {"esi_id": option.esi_id, "esi_code": f"C-{option.esi_id}"},
                            "address": {
                                "address_info": {"address_line_1": "1 Dealer Street"},
                                "district_info": {"district_id": option.district_id},
                                "pincode_info": {"pincode_id": "560001"},
                            },
                        }
                    ],
                }
                for option in self.ship_to
            ]
        }

    def _register_order(self, call: HumbeeCall) -> Any:
        if self.registration_timeouts:
            self.registration_timeouts -= 1
            raise httpx.ReadTimeout("fake read timeout")
        n = next(self._dp_numbers)
        return {
            "dp_order_id": f"dp-{n}",
            "dp_order_number": f"DP-{n:04d}",
            "status": "CREATED",
            "accepted_gross_total_paise": None,
        }


def install_commerce(fake: FakeHumbee) -> FakeCommerce:
    commerce = FakeCommerce()
    fake.route("GET", "/sfa/v1/outlets/{outlet_id}/sellers")(commerce._outlet_sellers)
    fake.route("GET", "/sfa/v1/manufacturers")(commerce._manufacturers)
    fake.route("GET", "/sfa/v1/products")(commerce._products)
    fake.route("POST", "/sfa/v1/schemes/evaluate")(commerce._evaluate_scheme)
    fake.route("GET", "/sfa/v1/purchase-orders")(commerce._purchase_orders)
    fake.route("GET", "/sfa/v1/sellers/ship-to-options")(commerce._ship_to_options)
    fake.route("POST", "/sfa/v1/orders")(commerce._register_order)
    return commerce
