from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

AS_OF = "2026-10-19T04:00:00+00:00"


class HumbeeFailure(Exception):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def _envelope(error_code: str, data: Any) -> httpx.Response:
    return httpx.Response(
        200,
        json={"error": error_code != "000", "error_code": error_code, "message": "fake", "data": data},
    )


@dataclass
class HumbeeCall:
    method: str
    path: str
    params: httpx.QueryParams
    json: Any
    headers: httpx.Headers
    path_params: dict[str, str]


Handler = Callable[[HumbeeCall], Any]


@dataclass
class District:
    district_id: str
    name: str
    state_id: str


@dataclass
class State:
    state_id: str
    name: str
    zone_id: str


@dataclass
class Zone:
    zone_id: str
    name: str


@dataclass
class Outlet:
    outlet_id: str
    name: str
    district_id: str
    shop_category_id: str = "CATEGORY_A"
    is_active: bool = True
    latitude: float | None = 12.9716
    longitude: float | None = 77.5946
    contact_mobile: str | None = "+919000000001"
    gstin: str | None = None
    pan: str | None = None


@dataclass
class FakeHumbee:
    zones: dict[str, Zone] = field(default_factory=dict)
    states: dict[str, State] = field(default_factory=dict)
    districts: dict[str, District] = field(default_factory=dict)
    outlets: dict[str, Outlet] = field(default_factory=dict)
    calls: list[HumbeeCall] = field(default_factory=list)
    unrouted: list[str] = field(default_factory=list)
    outlet_page_size: int = 2
    _routes: list[tuple[str, re.Pattern[str], str, Handler]] = field(default_factory=list)
    _failures: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.add_zone("1", "South")
        self.add_state("10", "Karnataka", zone_id="1")
        self.add_district("100", "Bengaluru Urban", state_id="10")
        self.add_district("101", "Mysuru", state_id="10")
        self.add_zone("2", "West")
        self.add_state("20", "Maharashtra", zone_id="2")
        self.add_district("200", "Pune", state_id="20")
        self.route("GET", "/sfa/v1/geography-zones")(self._zones)
        self.route("GET", "/sfa/v1/geography-states")(self._states)
        self.route("GET", "/sfa/v1/geography-districts")(self._districts)
        self.route("GET", "/sfa/v1/outlets")(self._search_outlets)
        self.route("GET", "/sfa/v1/outlets/{outlet_id}")(self._outlet_detail)

    def add_zone(self, zone_id: str, name: str) -> Zone:
        self.zones[zone_id] = Zone(zone_id, name)
        return self.zones[zone_id]

    def add_state(self, state_id: str, name: str, *, zone_id: str) -> State:
        self.states[state_id] = State(state_id, name, zone_id)
        return self.states[state_id]

    def add_district(self, district_id: str, name: str, *, state_id: str) -> District:
        self.districts[district_id] = District(district_id, name, state_id)
        return self.districts[district_id]

    def add_outlet(self, outlet_id: str, name: str | None = None, *, district_id: str = "100", **fields: Any) -> Outlet:
        self.outlets[outlet_id] = Outlet(outlet_id, name or f"Outlet {outlet_id}", district_id, **fields)
        return self.outlets[outlet_id]

    def route(self, method: str, template: str) -> Callable[[Handler], Handler]:
        pattern = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$")

        def register(handler: Handler) -> Handler:
            self._routes.insert(0, (method, pattern, template, handler))
            return handler

        return register

    def fail(self, method: str, template: str, error_code: str, *, times: int = 1) -> None:
        self._failures.setdefault((method, template), []).extend([error_code] * times)

    def calls_to(self, method: str, path: str) -> list[HumbeeCall]:
        return [call for call in self.calls if call.method == method and call.path == path]

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        for method, pattern, template, handler in self._routes:
            match = pattern.match(path)
            if method != request.method or match is None:
                continue
            call = HumbeeCall(
                method=request.method,
                path=path,
                params=request.url.params,
                json=json.loads(request.content) if request.content else None,
                headers=request.headers,
                path_params=match.groupdict(),
            )
            self.calls.append(call)
            queued = self._failures.get((method, template))
            if queued:
                return _envelope(queued.pop(0), None)
            try:
                return _envelope("000", handler(call))
            except HumbeeFailure as failure:
                return _envelope(failure.error_code, None)
        self.unrouted.append(f"{request.method} {path}")
        return httpx.Response(404, json={"detail": "FakeHumbee has no route"})

    def _zones(self, call: HumbeeCall) -> Any:
        return [{"zone_id": int(z.zone_id), "zone_name": z.name} for z in self.zones.values()]

    def _states(self, call: HumbeeCall) -> Any:
        wanted = call.params.get_list("zone_ids") or list(self.zones)
        return [
            {
                "zone_id": int(zone_id),
                "states": [
                    {"state_id": int(s.state_id), "state_name": s.name}
                    for s in self.states.values()
                    if s.zone_id == zone_id
                ],
            }
            for zone_id in wanted
            if zone_id in self.zones
        ]

    def _districts(self, call: HumbeeCall) -> Any:
        wanted = call.params.get_list("state_ids") or list(self.states)
        return [
            {
                "state_id": int(state_id),
                "districts": [
                    {"district_id": int(d.district_id), "district_name": d.name}
                    for d in self.districts.values()
                    if d.state_id == state_id
                ],
            }
            for state_id in wanted
            if state_id in self.states
        ]

    def _search_outlets(self, call: HumbeeCall) -> Any:
        district_ids = call.params.get_list("district_ids")
        categories = call.params.get_list("shop_category_ids")
        query = (call.params.get("query") or "").lower()
        matches = [
            o
            for o in self.outlets.values()
            if o.district_id in district_ids
            and (not categories or o.shop_category_id in categories)
            and query in o.name.lower()
        ]
        start = int(call.params.get("cursor") or 0)
        end = start + min(int(call.params["limit"]), self.outlet_page_size)
        page = matches[start:end]
        return {
            "as_of": AS_OF,
            "next_cursor": str(end) if end < len(matches) else None,
            "outlets": [
                {
                    "district_id": district_id,
                    "district_name": self.districts[district_id].name if district_id in self.districts else "",
                    "records": [
                        {
                            "outlet_id": o.outlet_id,
                            "name": o.name,
                            "shop_category_id": o.shop_category_id,
                            "gstin": o.gstin,
                            "pan": o.pan,
                        }
                        for o in page
                        if o.district_id == district_id
                    ],
                }
                for district_id in dict.fromkeys(o.district_id for o in page)
            ],
        }

    def _outlet_detail(self, call: HumbeeCall) -> Any:
        outlet = self.outlets.get(call.path_params["outlet_id"])
        if outlet is None:
            raise HumbeeFailure("030")
        return {
            "outlet_id": outlet.outlet_id,
            "name": outlet.name,
            "locality": "MG Road",
            "latitude": outlet.latitude,
            "longitude": outlet.longitude,
            "is_active": outlet.is_active,
            "contact_mobile": outlet.contact_mobile,
            "district": self.districts[outlet.district_id].name if outlet.district_id in self.districts else "",
            "contact_person": "Owner",
            "gstin": outlet.gstin,
            "pan": outlet.pan,
            "registered_address": "1 MG Road",
            "credit_limit_paise": None,
            "credit_outstanding_paise": None,
            "as_of": AS_OF,
        }
