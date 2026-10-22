"""The approvals engine's public contract — M06 §3a.

Everything a consuming module needs in order to plug a new subject type in lives here: the
canonical enums (§3a.2/§3a.3), the DTOs the engine renders generically, the
`ApprovalSubjectAdapter` Protocol (§3a.4) and the `SubjectTypeRegistry` whose completeness is a
fatal boot invariant (R-AP-03).

`approvals/service.py` calls **nothing** on a subject except the Protocol below. That is what keeps
"one approval engine, not five" true: adding expense approval tomorrow is a new adapter and a new
`SubjectType` value, not a change to the engine.

Two deliberate deviations from the Protocol as written in M06 §3a.4, both so adapters can honour
R-AP-16 ("apply_edit, the status transition, the decision row, the adapter callback and the
notification write all occur in one database transaction"):

* every method that touches the database takes the **caller's** `Session` as its first argument —
  an adapter must never open a session or a transaction of its own;
* the outcome callbacks return `list[SubjectEvent]` (a plain description of what happened) instead
  of ORM `DomainEvent` rows. The engine publishes them through `platform/domain_events.py` inside
  the decision transaction, so adapters never touch the event table directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from humbee_sfa.core.deps import AccessTokenClaims
from humbee_sfa.modules.approvals.models import Request

# ---------------------------------------------------------------------------
# Canonical enums (M06 §3a.2, §3a.3, §3.2) — these mirror the CHECK constraints on
# `approvals_requests` / `approvals_decisions` exactly. Changing one without the other is a bug.
# ---------------------------------------------------------------------------


class SubjectType(StrEnum):
    BEAT_CREATE = "beat_create"
    BEAT_EDIT = "beat_edit"
    DP_ORDER = "dp_order"
    LEAVE = "leave"
    OUTLET_VERIFICATION = "outlet_verification"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_EDITS = "approved_with_edits"
    AUTO_APPROVED = "auto_approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"  # reserved; unreachable in v1 (M06 §12 Q13)


class RoutingReason(StrEnum):
    DIRECT_PARENT = "direct_parent"
    ESCALATED_PARENT_ON_LEAVE = "escalated_parent_on_leave"
    AUTO_TOP_OF_HIERARCHY = "auto_top_of_hierarchy"


class DecisionAction(StrEnum):
    SUBMITTED = "submitted"
    ROUTED = "routed"
    ESCALATED = "escalated"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    WITHDRAWN = "withdrawn"


TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        ApprovalStatus.APPROVED,
        ApprovalStatus.APPROVED_WITH_EDITS,
        ApprovalStatus.AUTO_APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.WITHDRAWN,
        ApprovalStatus.EXPIRED,
    }
)
GRANTED_STATUSES: frozenset[str] = frozenset(
    {ApprovalStatus.APPROVED, ApprovalStatus.APPROVED_WITH_EDITS, ApprovalStatus.AUTO_APPROVED}
)

# Timeline step states — the four values `HM1.ApprovalTimeline` accepts (M06 §3.3). Not to be
# confused with `ApprovalStatus`; `edited` doubles as the escalation step (§12 Q6).
TIMELINE_DONE = "done"
TIMELINE_EDITED = "edited"
TIMELINE_CURRENT = "current"
TIMELINE_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Actor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Actor:
    """Who is acting. Adapters receive this instead of raw claims so they cannot re-derive scope."""

    tenant_id: str
    employee_id: str
    role: str

    @classmethod
    def from_claims(cls, claims: AccessTokenClaims) -> Actor:
        return cls(
            tenant_id=claims.tenant_id, employee_id=claims.employee_id, role=claims.role
        )

    @classmethod
    def system(cls, tenant_id: str) -> Actor:
        """The engine itself — auto-approval has no human actor."""

        return cls(tenant_id=tenant_id, employee_id="", role="system")


# ---------------------------------------------------------------------------
# Subject DTOs (M06 §3a.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectSummary:
    """Row content for S-AP1 / S-AP3. Denormalised onto the request at write time (M06 §5.1.4) so
    the inbox never calls back into a subject module or Humbee."""

    title: str
    subtitle: str
    icon_key: str
    requester_id: str
    amount_paise: int | None = None


@dataclass(frozen=True)
class SubjectDetailBlock:
    """One typed block on S-AP2. `kind` is one of `key_values`, `line_items`, `date_range`, `map`,
    `photo_grid`; the engine renders it generically and knows nothing about atta, beats or leave."""

    kind: str
    label: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SubjectDetailBlocks:
    blocks: tuple[SubjectDetailBlock, ...] = ()


@dataclass(frozen=True)
class EditableField:
    """One control in the S-AP2 Edit sheet. An empty list hides the Edit button (R-AP-13)."""

    key: str
    label: str
    kind: str  # `integer_stepper` | `date_range` | `text`
    current_value: Any = None
    min_value: int | None = None
    max_value: int | None = None


@dataclass(frozen=True)
class SubjectEvent:
    """A domain event an adapter wants published inside the decision transaction."""

    stream: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class EditResult:
    """`apply_edit` must bump `subject_version` and hand back the recomputed summary so the
    request's denormalised title/subtitle/amount stay correct (M06 §3a.4)."""

    summary: SubjectSummary
    subject_version: int
    patch_applied: dict[str, Any]
    events: list[SubjectEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovalAdvisory:
    """Non-blocking only — severity is never `blocking` (R-AP-19)."""

    code: str
    severity: str  # `info` | `warning`
    message: str


@dataclass(frozen=True)
class NotificationSpec:
    """Materialised strings, computed at write time (R-AP-22). Consumed by Story 2.3."""

    kind: str
    title: str
    recipient_id: str
    dedupe_key: str
    subtitle: str | None = None
    deep_link_type: str | None = None
    deep_link_id: str | None = None


@dataclass(frozen=True)
class DeepLink:
    target_type: str  # `order` | `beat` | `leave` | `outlet` | `approval_request`
    target_id: str


class SubjectEditRejected(Exception):
    """Raised by `apply_edit` on validation failure. The engine turns this into
    `422 SUBJECT_EDIT_REJECTED` and rolls the whole decision back (R-AP-16)."""

    def __init__(self, message: str, *, field_key: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field_key = field_key


# ---------------------------------------------------------------------------
# The subject-type contract (M06 §3a.4)
# ---------------------------------------------------------------------------


@runtime_checkable
class ApprovalSubjectAdapter(Protocol):
    """Implemented once per `SubjectType` by the owning module, registered at startup.

    Every method that reads or writes runs inside the engine's transaction on the `session` it is
    given (R-AP-16). None of them may commit, roll back, or open a session.
    """

    subject_type: SubjectType

    # ---- rendering -------------------------------------------------------

    def summary(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectSummary:
        """Row content for S-AP1 / S-AP3 / notification titles."""

    def detail(self, session: Session, *, subject_id: str, viewer: Actor) -> SubjectDetailBlocks:
        """Ordered, typed blocks rendered between the routing banner and the trail on S-AP2."""

    # ---- editing ---------------------------------------------------------

    def editable_fields(self, session: Session, *, subject_id: str) -> list[EditableField]:
        """`[]` means the Edit button is hidden for this subject type."""

    def apply_edit(
        self, session: Session, *, subject_id: str, patch: dict[str, Any], actor: Actor
    ) -> EditResult:
        """Validate + mutate the subject in the caller's transaction. MUST bump `subject_version`
        and return the recomputed summary. MUST raise `SubjectEditRejected` on validation failure."""

    # ---- outcome callbacks (all run in the decision transaction) ---------

    def on_approved(self, session: Session, *, request: Request) -> list[SubjectEvent]: ...

    def on_rejected(
        self, session: Session, *, request: Request, reason: str
    ) -> list[SubjectEvent]: ...

    def on_withdrawn(self, session: Session, *, request: Request) -> list[SubjectEvent]: ...

    # ---- advisory + notification -----------------------------------------

    def advisories(self, session: Session, *, subject_id: str) -> list[ApprovalAdvisory]: ...

    def notification(
        self, request: Request, outcome: ApprovalStatus, *, occurred_at: datetime
    ) -> NotificationSpec: ...

    def deep_link(self, request: Request, viewer: Actor) -> DeepLink: ...


# ---------------------------------------------------------------------------
# Registry (M06 §3a.1, R-AP-03)
# ---------------------------------------------------------------------------


class SubjectTypeRegistry:
    """Startup-populated plugin table. `validate_complete()` is what stops a sixth workflow
    quietly growing its own approval table: a `SubjectType` with no adapter is a **fatal boot
    error**, never a runtime 500 (R-AP-03)."""

    def __init__(self) -> None:
        self._adapters: dict[SubjectType, ApprovalSubjectAdapter] = {}

    def register(self, adapter: ApprovalSubjectAdapter, *, replace: bool = False) -> None:
        subject_type = SubjectType(adapter.subject_type)
        if subject_type in self._adapters and not replace:
            raise RuntimeError(
                f"An adapter for subject type {subject_type!r} is already registered; "
                "pass replace=True to re-register it."
            )
        self._adapters[subject_type] = adapter

    def get(self, subject_type: str) -> ApprovalSubjectAdapter:
        try:
            adapter = self._adapters[SubjectType(subject_type)]
        except (KeyError, ValueError) as exc:
            # Unreachable once `validate_complete()` has run at startup.
            raise RuntimeError(f"No approval adapter registered for {subject_type!r}.") from exc
        return adapter

    def registered_types(self) -> frozenset[SubjectType]:
        return frozenset(self._adapters)

    def validate_complete(self) -> None:
        missing = sorted(value for value in SubjectType if value not in self._adapters)
        if missing:
            raise RuntimeError(
                "Approval subject types without a registered adapter (R-AP-03): "
                + ", ".join(missing)
            )


registry = SubjectTypeRegistry()


__all__ = [
    "GRANTED_STATUSES",
    "TERMINAL_STATUSES",
    "Actor",
    "ApprovalAdvisory",
    "ApprovalStatus",
    "ApprovalSubjectAdapter",
    "DecisionAction",
    "DeepLink",
    "EditResult",
    "EditableField",
    "NotificationSpec",
    "RoutingReason",
    "SubjectDetailBlock",
    "SubjectDetailBlocks",
    "SubjectEditRejected",
    "SubjectEvent",
    "SubjectSummary",
    "SubjectType",
    "SubjectTypeRegistry",
    "registry",
]
