"""Provider-neutral port for the Humbee outlet master.

Every id is treated as an opaque string throughout — never parsed, never assumed numeric.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import HumbeeError, HumbeeNotFoundError, get_humbee_client

_SEARCH_PAGE_SIZE = 100


@dataclass(frozen=True)
class OutletRecord:
    external_id: str
    name: str
    locality: str | None
    category: str | None
    district_external_id: str | None
    lat: Decimal | None
    lng: Decimal | None
    as_of: datetime
    # `None` means "not checked yet" (search-derived), distinct from a confirmed `False`.
    is_active: bool | None = None
    contact_mobile: str | None = None
    district_name: str = ""  # detail's `district` field is a name, never an id
    contact_person: str | None = None
    gstin: str | None = None
    pan: str | None = None
    registered_address: str | None = None
    credit_limit_paise: int | None = None
    credit_outstanding_paise: int | None = None


@dataclass(frozen=True)
class OutletSearchPage:
    """One page of a C-2 search. `next_cursor` is `None` on the last page."""

    records: list[OutletRecord]
    next_cursor: str | None


@dataclass(frozen=True)
class CoordinateCorrectionResult:
    outlet_ref: str
    accepted: bool
    latitude: Decimal | None
    longitude: Decimal | None
    rejection_code: str | None


class OutletMasterUnavailable(RuntimeError):
    pass


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _int(value: Any) -> int | None:
    return None if value is None else int(value)


def _datetime(value: Any) -> datetime:
    if not value:
        raise ValueError("as_of is required")
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as_of must include a timezone offset")
    return parsed


def _documents(data: dict[str, Any]) -> tuple[str | None, str | None]:
    # Both optional throughout — `OutletRecord.gstin`/`.pan` are `str | None` and the projection
    # columns are nullable. An outlet genuinely can have neither on file; that's not a malformed
    # response worth a 5xx over.
    gstin = data.get("gstin") or None
    pan = data.get("pan") or None
    return str(gstin) if gstin is not None else None, str(pan) if pan is not None else None


def _record_from_search_item(
    item: dict[str, Any],
    *,
    district_id: str,
    as_of: datetime,
    district_name: str = "",
) -> OutletRecord:
    gstin, pan = _documents(item)
    return OutletRecord(
        external_id=str(item["outlet_id"]),
        name=item.get("name") or "",
        locality=None,
        category=item.get("shop_category_id") or None,
        district_external_id=district_id,
        lat=None,
        lng=None,
        district_name=district_name,
        gstin=gstin,
        pan=pan,
        as_of=as_of,
    )


def _record_from_detail(data: dict[str, Any]) -> OutletRecord:
    gstin, pan = _documents(data)
    return OutletRecord(
        external_id=str(data["outlet_id"]),
        name=data.get("name") or "",
        locality=data.get("locality") or None,
        category=None,  # C-3 carries no shop-category field at all
        district_external_id=None,
        lat=_decimal(data.get("latitude")),
        lng=_decimal(data.get("longitude")),
        is_active=data.get("is_active"),
        contact_mobile=data.get("contact_mobile"),
        district_name=data.get("district") or "",
        contact_person=data.get("contact_person"),
        gstin=gstin,
        pan=pan,
        registered_address=data.get("registered_address"),
        credit_limit_paise=_int(data.get("credit_limit_paise")),
        credit_outstanding_paise=_int(data.get("credit_outstanding_paise")),
        as_of=_datetime(data.get("as_of")),
    )


class HumbeeOutletMasterProvider:
    """C-2 search and singular C-3 detail adapter."""

    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def search(
        self, *, tenant_id: str, district_ids: list[str], category_ids: list[str], query: str | None
    ) -> list[OutletRecord]:
        """Every page of the search, for the validation paths that must see the whole scope.

        A picker should call `search_page` instead and let the user walk the pages.
        """

        records: list[OutletRecord] = []
        cursor: str | None = None
        while True:
            page = self.search_page(
                tenant_id=tenant_id,
                district_ids=district_ids,
                category_ids=category_ids,
                query=query,
                cursor=cursor,
                limit=_SEARCH_PAGE_SIZE,
            )
            records.extend(page.records)
            if not page.next_cursor:
                return records
            cursor = page.next_cursor

    def search_page(
        self,
        *,
        tenant_id: str,
        district_ids: list[str],
        category_ids: list[str],
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> OutletSearchPage:
        """Exactly one C-2 request. Pass a previous page's `next_cursor` back to walk forward."""

        del tenant_id  # derived from the api-key credential
        if not district_ids:
            return OutletSearchPage(records=[], next_cursor=None)
        try:
            return self._search_outlet_page_by_districts(
                district_ids=district_ids,
                category_ids=category_ids,
                query=query,
                cursor=cursor,
                limit=limit,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OutletMasterUnavailable(f"unexpected outlet search response shape: {exc}") from exc
        except HumbeeError as exc:
            raise OutletMasterUnavailable(str(exc)) from exc

    def _search_outlet_page_by_districts(
        self,
        *,
        district_ids: list[str],
        category_ids: list[str],
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> OutletSearchPage:
        """Fetch one page of outlets across every district in the filter.

        C-2 pages across districts rather than within one, so a district's group can span pages —
        callers merge groups themselves rather than assuming one group per district per page.
        """

        params: dict[str, Any] = {"district_ids": district_ids, "limit": limit}
        if category_ids:
            params["shop_category_ids"] = category_ids
        if query:
            params["query"] = query
        if cursor:
            params["cursor"] = cursor
        data = self._client.call(
            "outlets.search", "GET", "/sfa/v1/outlets", route="/outlets", params=params
        )
        as_of = _datetime(data.get("as_of"))
        # Verified 2026-08-29: `outlets` is a list of per-district groups
        # ({district_id, district_name, records, total_count}), not a flat outlet list.
        records = [
            _record_from_search_item(
                item,
                district_id=str(group["district_id"]),
                district_name=str(group.get("district_name") or ""),
                as_of=as_of,
            )
            for group in data.get("outlets") or []
            for item in group.get("records") or []
        ]
        return OutletSearchPage(records=records, next_cursor=data.get("next_cursor") or None)

    def fetch_by_id(self, *, tenant_id: str, outlet_id: str) -> OutletRecord | None:
        del tenant_id
        try:
            data = self._client.call(
                "outlets.detail", "GET", f"/sfa/v1/outlets/{outlet_id}",
                route="/outlets/{id}",
            )
        except HumbeeNotFoundError:
            return None
        except HumbeeError as exc:
            raise OutletMasterUnavailable(str(exc)) from exc
        try:
            return _record_from_detail(data)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OutletMasterUnavailable(
                f"unexpected outlet detail response shape: {exc}"
            ) from exc

    def submit_coordinate_correction(
        self,
        *,
        tenant_id: str,
        outlet_id: str,
        latitude: Decimal,
        longitude: Decimal,
        accuracy_m: Decimal,
        provider: str,
        captured_at: datetime,
        captured_by: str,
        idempotency_key: str,
    ) -> CoordinateCorrectionResult:
        del tenant_id
        data = self._client.call(
            "outlets.coordinates",
            "PATCH",
            f"/sfa/v1/outlets/{outlet_id}/coordinates",
            route="/outlets/{id}/coordinates",
            json_body={
                "latitude": float(latitude),
                "longitude": float(longitude),
                "accuracy_m": float(accuracy_m),
                "provider": provider,
                "captured_at": captured_at.isoformat(),
                "captured_by": captured_by,
            },
            idempotency_key=idempotency_key,
            max_retries=0,  # resubmission is the offline queue replaying, not an in-client retry
        )
        return CoordinateCorrectionResult(
            outlet_ref=str(data.get("outlet_id", outlet_id)),
            accepted=bool(data.get("accepted")),
            latitude=_decimal(data.get("latitude")),
            longitude=_decimal(data.get("longitude")),
            rejection_code=data.get("rejection_code") or data.get("rejection_reason"),
        )

