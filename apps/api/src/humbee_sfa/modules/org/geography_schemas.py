"""Geography request and response DTOs.

Field names follow the canonical geo-scope JSON in M03 §3a.3 (`zones`/`states`/`districts`) so the
API, the picker component and the spec all use one vocabulary.

No shop-category or outlet-count fields anywhere here: they were dropped end to end when G-2/G-3/
G-4 (SFA-API-Contract v2.2) replaced the old single-call geography master, the only source either
ever had (epics/humbee-sfa-build/07-humbee-real-integration.md Story 7.2, reconciled 2026-09-03).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

_ID_LIST = Field(default_factory=list)


class GeoLabel(BaseModel):
    """`{id, name}` snapshot for a zone/state, taken at assignment time (epic 07 Story 7.2) — the
    master cache that used to let a stored id resolve back to a name is gone."""

    id: str
    name: str


class DistrictLabel(BaseModel):
    """Districts also carry their state, since district names are not unique across states
    (`PRATAPGARH` occurs in both UP and Rajasthan)."""

    id: str
    name: str
    state_id: str
    state_name: str


class GeoLabels(BaseModel):
    zones: list[GeoLabel] = Field(default_factory=list)
    states: list[GeoLabel] = Field(default_factory=list)
    districts: list[DistrictLabel] = Field(default_factory=list)


class ZoneOption(BaseModel):
    id: str
    name: str


class StateOption(BaseModel):
    id: str
    zone_id: str
    name: str


class DistrictOption(BaseModel):
    id: str
    state_id: str
    name: str


class ZonesResponse(BaseModel):
    zones: list[ZoneOption]


class StatesResponse(BaseModel):
    states: list[StateOption]


class DistrictsResponse(BaseModel):
    districts: list[DistrictOption]


class GeoScopeResponse(BaseModel):
    employee_id: str
    zones: list[str]
    states: list[str]
    districts: list[str]
    geo_labels: GeoLabels
    assigned_by: str | None
    assigned_at: datetime | None


class AssignGeoScopeBody(BaseModel):
    """`districts` must be non-empty (R-ORG-30)."""

    zones: list[str] = _ID_LIST
    states: list[str] = _ID_LIST
    districts: list[str] = Field(min_length=1)
