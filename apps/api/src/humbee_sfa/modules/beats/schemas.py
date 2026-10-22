"""Beats HTTP DTOs — M07 §10.

`geo_scope` and `frequency` are stored as `jsonb` value objects (M07 §3.4/§3.5) and are passed
through largely as-is; only the fields the wizard screens (S-BEAT2–4, S-BEAT7) actually write are
modelled here.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ShopCategory(str, Enum):
    """Stable Humbee shop-category identifiers used for filtering and persistence."""

    CATEGORY_A = "CATEGORY_A"
    CATEGORY_B = "CATEGORY_B"
    CATEGORY_C = "CATEGORY_C"
    CATEGORY_D = "CATEGORY_D"
    CATEGORY_E = "CATEGORY_E"
    CATEGORY_F = "CATEGORY_F"


def to_shop_category(value: str | None) -> ShopCategory | None:
    """Coerce a stored category id into the enum, degrading to `None` when Humbee publishes one we
    do not know. An unrecognised category must never fail a beat read."""

    if value is None:
        return None
    try:
        return ShopCategory(value)
    except ValueError:
        return None


class GeoScope(BaseModel):
    """Full replacement object. Omitted keys must not become `[]` and wipe stored scope."""

    zones: list[str]
    states: list[str]
    districts: list[str]
    cats: list[ShopCategory]


class ShopCategoriesResponse(BaseModel):
    categories: list[ShopCategory]


class Frequency(BaseModel):
    frequency: Literal["daily", "weekly", "fortnightly", "monthly"]
    visit_days: list[int] = Field(default_factory=list)
    week_cycle: list[int] = Field(default_factory=list)


class BeatOutletItem(BaseModel):
    outlet_ref: str
    name: str
    locality: str | None
    category: ShopCategory | None
    sequence_hint: int | None


class BeatListItem(BaseModel):
    id: str
    code: str
    display_name: str
    owner_employee_id: str
    lifecycle_state: str
    activation_state: str
    display_status: str
    outlet_count: int
    frequency: dict[str, Any]
    run_origin: Literal["assigned_beat", "unplanned_beat"] | None = None
    planned_for_business_date: bool | None = None
    created_at: datetime


class BeatListResponse(BaseModel):
    business_date: date
    items: list[BeatListItem]
    facets: dict[str, int]
    total: int


class PendingEditSummary(BaseModel):
    state: str
    diff: list[dict[str, Any]]
    approval_request_id: str | None
    submitted_at: datetime


class BeatDetailResponse(BaseModel):
    id: str
    version_id: str
    version_state: str
    code: str
    display_name: str
    owner_employee_id: str
    lifecycle_state: str
    activation_state: str
    display_status: str
    geo_scope: dict[str, Any]
    frequency: dict[str, Any]
    outlet_count: int
    outlets: list[BeatOutletItem]
    approval_request_id: str | None
    created_at: datetime
    deactivation_reason: str | None
    deactivated_at: datetime | None
    pending_edit: PendingEditSummary | None


class CreateBeatBody(BaseModel):
    """S-BEAT2 entry (transition #1). `id` is the client-generated ULID (idempotent create).
    `owner_employee_id` lets an Admin/Manager create the beat for a salesperson; omitted, the
    caller becomes the owner."""

    id: str | None = Field(default=None, min_length=26, max_length=26)
    owner_employee_id: str | None = Field(default=None, min_length=1, max_length=26)


class PatchDraftBody(BaseModel):
    """Autosave for S-BEAT2 (`geo_scope`) and S-BEAT4 (`display_name`, `frequency`)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"\S")
    code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"\S")
    geo_scope: GeoScope | None = None
    frequency: Frequency | None = None


class DraftOutletsBody(BaseModel):
    outlet_refs: list[str]

class ScopeOutletItem(BaseModel):
    outlet_ref: str
    name: str
    locality: str | None
    category: ShopCategory | None
    selected: bool
    taken_by_beat: str | None


class ScopeOutletsResponse(BaseModel):
    items: list[ScopeOutletItem]
    next_cursor: str | None


class BranchEditResponse(BaseModel):
    beat_id: str
    base_version_id: str
    proposed_version_id: str


class DeactivateBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminUpdateBeatBody(BaseModel):
    """Admin-only immediate edit (R-BEAT-17) — applies without approval."""

    display_name: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"\S")
    owner_employee_id: str | None = Field(default=None, min_length=1, max_length=26)
    geo_scope: GeoScope | None = None
    frequency: Frequency | None = None
    outlet_refs: list[str] | None = None
