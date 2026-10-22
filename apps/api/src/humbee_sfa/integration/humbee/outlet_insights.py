"""Humbee outlet insights — the club/benefits, performance, rewards and profiler sections.

Every section is keyed by the same triple: outlet, manufacturer and `outlet_esi_id`. The ESI is
load-bearing rather than incidental — sales and allocation belong to an ERP registration, so an
outlet holding two registrations under one manufacturer has two different answers.

The three data sections are passed through structurally unchanged. Humbee declares no response
schema for them, phase 1 is explicitly placeholder, and every figure arrives pre-formatted for
display ("100.00 Ton", "Amount: ₹ 5,00,000", "84.46%") — there is no number here to compute
with and no field whose meaning is ours to fix. Re-modelling that into typed SFA fields would
freeze a placeholder shape into our own contract and break when the real content lands. `as_of` is
lifted out because it is the one value SFA reasons about.

The profiler URL carries a pre-authenticated token that decodes to the outlet owner's phone number.
It must never be logged or persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import HumbeeError, get_humbee_client

InsightSectionName = Literal["benefits", "performance", "rewards"]


@dataclass(frozen=True)
class InsightSection:
    # Humbee's display tree for one section, verbatim.
    data: dict[str, Any]
    as_of: datetime | None


@dataclass(frozen=True)
class OutletInsightEsiRecord:
    esi_id: str
    esi_code: str
    active: bool


@dataclass(frozen=True)
class OutletInsightManufacturer:
    manufacturer_id: str
    manufacturer_name: str
    external_system_records: tuple[OutletInsightEsiRecord, ...]


@dataclass(frozen=True)
class OutletInsightManufacturersSnapshot:
    manufacturers: tuple[OutletInsightManufacturer, ...]
    as_of: datetime | None


class OutletInsightsUnavailable(RuntimeError):
    """An outlet insight section could not be read."""


class HumbeeOutletInsightsProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def get_section(
        self, section: InsightSectionName, *, outlet_id: str, manufacturer_id: str,
        outlet_esi_id: str,
    ) -> InsightSection:
        try:
            data = self._call(
                section, outlet_id=outlet_id, manufacturer_id=manufacturer_id,
                outlet_esi_id=outlet_esi_id,
            )
            payload = dict(data)
            as_of_raw = payload.pop("as_of", None)
            as_of = datetime.fromisoformat(as_of_raw) if as_of_raw else None
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OutletInsightsUnavailable(
                f"unexpected outlet {section} response shape: {exc}"
            ) from exc
        return InsightSection(data=payload, as_of=as_of)

    def get_profiler_url(
        self, *, outlet_id: str, manufacturer_id: str, outlet_esi_id: str
    ) -> str:
        try:
            data = self._call(
                "profiler", outlet_id=outlet_id, manufacturer_id=manufacturer_id,
                outlet_esi_id=outlet_esi_id,
            )
            url: str = data["url"]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OutletInsightsUnavailable(
                f"unexpected outlet profiler response shape: {exc}"
            ) from exc
        return url

    def get_manufacturers(self, *, outlet_id: str) -> OutletInsightManufacturersSnapshot:
        try:
            data = self._client.call(
                "outlet_insights.manufacturers",
                "GET",
                "/sfa/v1/outlets/insights/manufacturers",
                route="/outlets/insights/manufacturers",
                params={"outlet_id": outlet_id},
            )
            manufacturers = tuple(
                OutletInsightManufacturer(
                    manufacturer_id=item["manufacturer_id"],
                    manufacturer_name=item["manufacturer_name"],
                    external_system_records=tuple(
                        OutletInsightEsiRecord(
                            esi_id=esi["esi_id"],
                            esi_code=esi["esi_code"],
                            active=esi["active"],
                        )
                        for esi in item["external_system_records"]
                    ),
                )
                for item in data["manufacturers"]
            )
            as_of_raw = data.get("as_of")
            as_of = datetime.fromisoformat(as_of_raw) if as_of_raw else None
        except HumbeeError as exc:
            raise OutletInsightsUnavailable(str(exc)) from exc
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise OutletInsightsUnavailable(
                f"unexpected outlet manufacturers response shape: {exc}"
            ) from exc
        return OutletInsightManufacturersSnapshot(manufacturers=manufacturers, as_of=as_of)

    def _call(
        self, name: str, *, outlet_id: str, manufacturer_id: str, outlet_esi_id: str
    ) -> Any:
        try:
            return self._client.call(
                f"outlet_insights.{name}",
                "GET",
                f"/sfa/v1/outlets/insights/{name}",
                route=f"/outlets/insights/{name}",
                params={
                    "outlet_id": outlet_id,
                    "manufacturer_id": manufacturer_id,
                    "outlet_esi_id": outlet_esi_id,
                },
            )
        except HumbeeError as exc:
            raise OutletInsightsUnavailable(str(exc)) from exc


__all__ = [
    "HumbeeOutletInsightsProvider",
    "InsightSection",
    "InsightSectionName",
    "OutletInsightEsiRecord",
    "OutletInsightManufacturer",
    "OutletInsightManufacturersSnapshot",
    "OutletInsightsUnavailable",
]
