"""Humbee seller linkage.

Order routing (PO-backed vs direct, manager-approval-required or not) comes from the outlet's real
commercial relationships — per brand, per seller — never from an outlet-level tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import HumbeeError, get_humbee_client

KNOWN_SELLER_TYPES = frozenset({"MANUFACTURER", "R1", "R2", "R3", "R4"})


@dataclass(frozen=True)
class EsiRecord:
    esi_id: str
    esi_code: str
    geographic_info: dict[str, Any] | None = None


@dataclass(frozen=True)
class SellerRecord:
    external_id: str
    seller_type: str
    name: str
    address: str | None
    is_active: bool
    requires_purchase_order: bool
    manager_approval_required: bool
    # The seller's own ESI registrations — empty when seller_type is MANUFACTURER. One of these
    # is chosen as seller_esi_id on a secondary order.
    seller_esi_records: tuple[EsiRecord, ...]
    # The outlet's ESI registrations against this specific seller. One of these is chosen as
    # buyer_esi_id, regardless of order path.
    outlet_esi_records: tuple[EsiRecord, ...]


@dataclass(frozen=True)
class BrandSellers:
    brand_id: str
    brand_name: str
    sellers: tuple[SellerRecord, ...]
    # False means Humbee returned a widened fallback list, not a district-scoped one.
    filtered_by_district: bool


@dataclass(frozen=True)
class OutletSellersSnapshot:
    # zero brands/sellers is common and valid — never raised as SellerLinkageUnavailable
    outlet_id: str
    brands: tuple[BrandSellers, ...]
    total_count: int
    as_of: datetime


class SellerLinkageUnavailable(RuntimeError):
    pass


logger = structlog.get_logger("humbee_sfa.integration.humbee.seller")


def _first(entry: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in entry and entry[key] is not None:
            return entry[key]
    return None


def _parse_esi_records(raw: Any) -> tuple[EsiRecord, ...]:
    return tuple(
        EsiRecord(
            esi_id=str(item["esi_id"]),
            esi_code=str(item.get("esi_code") or ""),
            geographic_info=(
                item.get("geographic_info")
                if isinstance(item.get("geographic_info"), dict)
                else None
            ),
        )
        for item in raw or []
        if item.get("esi_id") is not None
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _address_from_components(entry: dict[str, Any]) -> str | None:
    parts = [
        _text(_first(entry, "address_line_1", "address_line1", "line1")),
        _text(_first(entry, "address_line_2", "address_line2", "line2")),
        _text(_first(entry, "address_line_3", "address_line3", "line3")),
        _text(_first(entry, "locality", "location", "landmark")),
        _text(_first(entry, "district_name", "district")),
        _text(_first(entry, "state_name", "state")),
        _text(_first(entry, "pincode", "pin_code", "postal_code")),
    ]
    filtered = [part for part in parts if part]
    return ", ".join(filtered) if filtered else None


def _parse_address(entry: dict[str, Any]) -> str | None:
    raw = _first(entry, "registered_address", "address", "seller_address")
    if raw is not None:
        try:
            parts = [
                _text(raw.get("address_line_1") or raw.get("address_line1") or raw.get("line1")),
                _text(raw.get("address_line_2") or raw.get("address_line2") or raw.get("line2")),
                _text(raw.get("address_line_3") or raw.get("address_line3") or raw.get("line3")),
                _text(raw.get("locality") or raw.get("location") or raw.get("landmark")),
                _text(raw.get("district_name") or raw.get("district")),
                _text(raw.get("state_name") or raw.get("state")),
                _text(raw.get("pincode") or raw.get("pin_code") or raw.get("postal_code")),
            ]
            filtered = [part for part in parts if part]
            if filtered:
                return ", ".join(filtered)
        except AttributeError:
            direct = _text(raw)
            if direct:
                return direct
    return _address_from_components(entry)


def _parse_seller(entry: dict[str, Any], *, brand_id: str) -> SellerRecord | None:
    seller_id = _first(entry, "seller_id", "id", "external_id")
    seller_type = entry.get("seller_type")
    name = _first(entry, "name", "seller_name")
    if seller_id is None or seller_type is None or name is None:
        logger.warning(
            "humbee_seller_field_missing", capability="seller.outlet_sellers", brand_id=brand_id
        )
        return None
    seller_type = str(seller_type).upper()
    if seller_type not in KNOWN_SELLER_TYPES:
        logger.warning(
            "humbee_seller_type_unknown",
            capability="seller.outlet_sellers",
            brand_id=brand_id,
            seller_type=seller_type,
        )
        return None
    return SellerRecord(
        external_id=str(seller_id),
        seller_type=seller_type,
        name=str(name),
        address=_parse_address(entry),
        is_active=bool(entry.get("is_active")),
        requires_purchase_order=bool(entry.get("requires_purchase_order")),
        manager_approval_required=bool(entry.get("manager_approval_required")),
        seller_esi_records=_parse_esi_records(entry.get("seller_esi_records")),
        outlet_esi_records=_parse_esi_records(entry.get("outlet_esi_records")),
    )


def _parse_brand_group(entry: dict[str, Any]) -> BrandSellers | None:
    brand_name = _first(entry, "brand_name", "name", "brand")
    # Newer Humbee builds carry `brand_id`; older dev responses only had the display brand name.
    brand_id = _first(entry, "brand_id", "id") or brand_name
    if brand_name is None:
        logger.warning("humbee_seller_brand_field_missing", capability="seller.outlet_sellers")
        return None
    raw_sellers = entry.get("sellers") or []
    sellers = tuple(
        seller
        for raw in raw_sellers
        if (seller := _parse_seller(raw, brand_id=str(brand_id))) is not None
    )
    filtered_by_district = bool(entry.get("sellers_filtered_by_district"))
    return BrandSellers(
        brand_id=str(brand_id), brand_name=str(brand_name), sellers=sellers,
        filtered_by_district=filtered_by_district,
    )


class HumbeeSellerLinkageProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def get_outlet_sellers(self, *, tenant_id: str, outlet_id: str) -> OutletSellersSnapshot:
        del tenant_id  # scoped by outlet id and the api-key alone
        try:
            data = self._client.call(
                "seller.outlet_sellers", "GET", f"/sfa/v1/outlets/{outlet_id}/sellers",
                route="/outlets/{id}/sellers",
            )
        except HumbeeError as exc:
            raise SellerLinkageUnavailable(str(exc)) from exc

        try:
            brands = tuple(
                group
                for raw in data.get("sellers_by_brand") or []
                if (group := _parse_brand_group(raw)) is not None
            )
            as_of_raw = data.get("as_of")
            as_of = datetime.fromisoformat(as_of_raw) if as_of_raw else datetime.now(UTC)
            total_count = data.get("total_count")
            if not isinstance(total_count, int):
                total_count = sum(len(group.sellers) for group in brands)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise SellerLinkageUnavailable(
                f"unexpected outlet sellers response shape: {exc}"
            ) from exc
        return OutletSellersSnapshot(
            outlet_id=outlet_id, brands=brands, total_count=total_count, as_of=as_of
        )
