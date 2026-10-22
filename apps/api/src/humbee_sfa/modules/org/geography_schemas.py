"""Geography request and response DTOs.

Field names follow the canonical geo-scope JSON (`zones`/`states`/`districts`) so the API and
the picker component use one vocabulary.

No shop-category or outlet-count fields anywhere here: they were dropped end to end when the
per-level geography endpoints replaced the old single-call geography master, the only source
either ever had.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

_ID_LIST: list[str] = Field(default_factory=list)


class GeoLabel(BaseModel):
    """`{id, name}` snapshot for a zone/state, taken at assignment time — the
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
    """`districts` must be non-empty."""

    zones: list[str] = _ID_LIST
    states: list[str] = _ID_LIST
    districts: list[str] = Field(min_length=1)
