"""Provider-neutral port for Humbee geography reads (M03 §3a.1, R-ORG-35).

Humbee owns the upstream geography master. SFA persists employee geography assignments and their
label projections in `modules/org`; this module holds the upstream records and the adapter.

G-2/G-3/G-4 (SFA-API-Contract v2.2) serve the zone → state → district tree one level at a time,
for a picker that drills down rather than loading the whole tree up front.
They expose neither a shop-category taxonomy nor district outlet counts, so geography assignment
contains neither.

OPEN DECISION — the `Location` level.
    Humbee exposes Zone / State / District and *no* `Location` level, which some downstream
    screens ask for. That gap is an unresolved product/data decision
    (`epics/humbee-sfa-build/EPIC.md` line "Humbee G-1 does not currently provide the `Location`
    level required by geography assignment"; `epics/humbee-sfa-build/01-organization-identity-
    access.md` Story 1.2; and `docs/rpi/2026-08-22-backend-epic-restructure/research.md`
    §"Location"). This module therefore deliberately has **no** `Location` record type and no
    `fetch_locations` method: inventing one would bake a guess at Humbee's API into the
    assignment contract. Do not add one until the decision lands in
    `docs/features/M03-org-workforce-and-geography.md`.

    Not answered by `GET /sfa/v1/locations` (C-16, `integration/humbee/onboarding.py`): that
    endpoint returns two flat, mutually-filterable lists (localities, pincodes) scoped to one
    district for address entry, with no assignment/pool semantics — a different concept from the
    hierarchical tier this decision is about.
"""

from __future__ import annotations

from dataclasses import dataclass

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import HumbeeError, get_humbee_client


@dataclass(frozen=True)
class ZoneOption:
    external_id: str
    name: str


@dataclass(frozen=True)
class StateOption:
    external_id: str
    zone_external_id: str
    name: str


@dataclass(frozen=True)
class DistrictOption:
    external_id: str
    state_external_id: str
    name: str


class GeographyMasterUnavailable(RuntimeError):
    """The upstream master could not be read."""


_ZONES_CAPABILITY = "geography.zones"
_ZONES_PATH = "/sfa/v1/geography-zones"
_STATES_CAPABILITY = "geography.states"
_STATES_PATH = "/sfa/v1/geography-states"
_DISTRICTS_CAPABILITY = "geography.districts"
_DISTRICTS_PATH = "/sfa/v1/geography-districts"
_TIMEOUT_S = 30.0
_MAX_RETRIES = 1


class HumbeeGeographyMasterProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_zones(self, *, tenant_id: str) -> tuple[ZoneOption, ...]:
        del tenant_id  # G-2 takes no parameters; one zone list for the whole master
        client = get_humbee_client(self._settings)
        try:
            data = client.call(
                _ZONES_CAPABILITY, "GET", _ZONES_PATH, timeout_s=_TIMEOUT_S, max_retries=_MAX_RETRIES
            )
            return tuple(
                ZoneOption(external_id=str(row["zone_id"]), name=str(row["zone_name"]))
                for row in data or []
            )
        except HumbeeError as exc:
            raise GeographyMasterUnavailable(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise GeographyMasterUnavailable(f"unexpected geography zones response shape: {exc}") from exc

    def fetch_states(self, *, tenant_id: str, zone_ids: list[str]) -> tuple[StateOption, ...]:
        del tenant_id
        client = get_humbee_client(self._settings)
        params = {"zone_ids": zone_ids} if zone_ids else None
        try:
            data = client.call(
                _STATES_CAPABILITY, "GET", _STATES_PATH,
                params=params, timeout_s=_TIMEOUT_S, max_retries=_MAX_RETRIES,
            )
            return tuple(
                StateOption(
                    external_id=str(state["state_id"]),
                    zone_external_id=str(group["zone_id"]),
                    name=str(state["state_name"]),
                )
                for group in data or []
                for state in group.get("states") or []
            )
        except HumbeeError as exc:
            raise GeographyMasterUnavailable(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise GeographyMasterUnavailable(f"unexpected geography states response shape: {exc}") from exc

    def fetch_districts(self, *, tenant_id: str, state_ids: list[str]) -> tuple[DistrictOption, ...]:
        del tenant_id
        client = get_humbee_client(self._settings)
        params = {"state_ids": state_ids} if state_ids else None
        try:
            data = client.call(
                _DISTRICTS_CAPABILITY, "GET", _DISTRICTS_PATH,
                params=params, timeout_s=_TIMEOUT_S, max_retries=_MAX_RETRIES,
            )
            return tuple(
                DistrictOption(
                    external_id=str(district["district_id"]),
                    state_external_id=str(group["state_id"]),
                    name=str(district["district_name"]),
                )
                for group in data or []
                for district in group.get("districts") or []
            )
        except HumbeeError as exc:
            raise GeographyMasterUnavailable(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise GeographyMasterUnavailable(f"unexpected geography districts response shape: {exc}") from exc

    def fetch_state_of_district(self, *, tenant_id: str, district_id: str) -> str | None:
        """The state a district belongs to, or `None` when the master does not know the district.

        G-4 offers no by-district lookup, so this reads the whole district master (748 rows) and
        matches locally. A caller that already holds a state must not use it. It exists because
        C-15 serviceability is bounded by state and two of the order flow's three checks hold only
        a district id.
        """

        return next(
            (
                district.state_external_id
                for district in self.fetch_districts(tenant_id=tenant_id, state_ids=[])
                if district.external_id == district_id
            ),
            None,
        )
