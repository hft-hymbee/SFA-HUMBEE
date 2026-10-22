"""Beats HTTP routes — M07 §10.

Handlers validate and translate HTTP only; transaction ownership and scope resolution are the
service's. Decisions on a submitted beat or beat edit are **not** here by design — they go through
`POST /api/v1/approvals/{approval_request_id}/{approve|reject|withdraw}` (R-AP-01), using the
`approval_request_id` carried on the beat detail response (`approval_request_id` / `pending_edit`).

Endpoints intentionally **not** built, matching M07 §10/§12 and Story 2.4's precedent of naming
skips explicitly:
- `GET /beats/code-available` — advisory-only early check; the DB unique constraint at submit is
  the authoritative one (M07 §10), so it is not worth a second code path.
- `GET /beats/{beat_id}/outlets` (paginated) — the beat detail response embeds the full outlet
  list; beat sizes in this product are tens of outlets, not thousands, so pagination adds
  complexity no real beat needs yet.
- `GET /beats/{beat_id}/versions` — "no prototype screen yet" per M07 §10 itself.
- `POST /beats/{beat_id}/withdraw-submission` and a `{id}`-addressed edit-request sub-resource —
  folded into the generic approvals withdraw endpoint and into `/draft` + `/edit-requests/submit`
  respectively, since a beat has at most one in-flight draft/edit at a time
  (`uq_beats_versions_one_pending`, `uq_beats_edit_one_pending`).
- `DELETE /beats/{beat_id}` — deliberately absent; no hard delete exists (R-BEAT-20).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.beats import schemas
from humbee_sfa.modules.beats.service import BeatService
from humbee_sfa.platform.telemetry.middleware import get_request_id

router = APIRouter(prefix="/api/v1", tags=["Beats"])

BeatId = Annotated[str, Path(min_length=1, max_length=26)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]


async def _read_raw_body(request: HttpRequest) -> bytes:
    return await request.body()


RawBody = Annotated[bytes, Depends(_read_raw_body)]


@router.get("/beats/shop-categories", response_model=schemas.ShopCategoriesResponse)
def list_shop_categories(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
) -> dict[str, Any]:
    """The beat outlet-category filter's fixed `CATEGORY_A`..`CATEGORY_F` identifiers
    (`schemas.ShopCategory`) — baked into SFA's own backend, never a Humbee call, unlike the
    zone/state/district pickers under `/org/geography/*`."""

    return schemas.ShopCategoriesResponse(categories=list(schemas.ShopCategory)).model_dump(mode="json")


@router.get("/beats", response_model=schemas.BeatListResponse)
def list_beats(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    beat_status: Annotated[str | None, Query(alias="status", pattern=r"^(all|approved|pending|draft)$")] = None,
    business_date: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Serves S-BEAT1 (owner scope) and S-BEAT6 (org scope) — the same path, scope-resolved
    server-side (M07 §10)."""

    return BeatService(session).list_beats(
        claims=claims, status_filter=beat_status, business_date=business_date, limit=limit, offset=offset
    )


@router.post("/beats", response_model=schemas.BeatDetailResponse, status_code=201)
def create_beat(
    body: schemas.CreateBeatBody,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    status_code, payload = BeatService(session).create_beat(claims=claims, body=body)
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/beats/{beat_id}", response_model=schemas.BeatDetailResponse)
def get_beat(
    beat_id: BeatId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return BeatService(session).get_beat_detail(claims=claims, beat_id=beat_id)


@router.get("/beats/{beat_id}/draft", response_model=schemas.BeatDetailResponse)
def get_beat_draft(
    beat_id: BeatId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The version pending approval, never the live one — `404 no_pending_version` if the beat has
    no draft right now."""

    return BeatService(session).get_beat_draft(claims=claims, beat_id=beat_id)


@router.patch("/beats/{beat_id}/draft", response_model=schemas.BeatDetailResponse)
def update_draft(
    beat_id: BeatId,
    body: schemas.PatchDraftBody,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Autosave for S-BEAT2 (`geo_scope`) and S-BEAT4 (`display_name`, `frequency`)."""

    return BeatService(session).update_draft(claims=claims, beat_id=beat_id, body=body)


@router.get("/beats/{beat_id}/scope-outlets", response_model=schemas.ScopeOutletsResponse)
def search_scope_outlets(
    beat_id: BeatId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    district_ids: Annotated[list[str] | None, Query()] = None,
    shop_categories: Annotated[list[schemas.ShopCategory] | None, Query()] = None,
) -> dict[str, Any]:
    """S-BEAT3 outlet pool, proxied from Humbee via `integration/humbee/outlet.py`.

    Paged: pass the previous response's `next_cursor` back as `cursor`. A null `next_cursor` is
    the last page. Never construct or parse a cursor — it is opaque to us and to the client.
    `district_ids` (+ optional `shop_categories`) browse an unsaved scope.
    """

    return BeatService(session).search_scope_outlets(
        claims=claims, beat_id=beat_id, query=q, cursor=cursor, limit=limit,
        district_ids=district_ids, shop_categories=shop_categories,
    )


@router.put("/beats/{beat_id}/draft/outlets", response_model=schemas.BeatDetailResponse)
def replace_draft_outlets(
    beat_id: BeatId,
    body: schemas.DraftOutletsBody,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return BeatService(session).replace_draft_outlets(claims=claims, beat_id=beat_id, body=body)


@router.post("/beats/{beat_id}/draft/discard", response_model=schemas.BeatDetailResponse)
def discard_draft(
    beat_id: BeatId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """S-BEAT7 "Discard" — abandons an in-progress edit and falls back to the current approved
    version. Naturally idempotent (discarding when nothing is pending is a no-op), so no
    `Idempotency-Key` is required."""

    return BeatService(session).discard_draft(claims=claims, beat_id=beat_id)


@router.post(
    "/beats/{beat_id}/submit",
    response_model=schemas.BeatDetailResponse,
    status_code=202,
    responses={200: {"model": schemas.BeatDetailResponse, "description": "Approved on submit"}},
)
def submit_beat(
    beat_id: BeatId,
    request: HttpRequest,
    raw_body: RawBody,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Transition #3 (S-BEAT4 "Submit for approval") — `202` when it enters the approval queue,
    `200` when an Admin or Manager submits a beat they built for a Sales Person and it lands
    approved straight away (R-BEAT-17)."""

    status_code, payload = BeatService(session).submit_beat(
        claims=claims, beat_id=beat_id, idempotency_key=idempotency_key,
        raw_body=raw_body, request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/beats/{beat_id}/edit-requests", response_model=schemas.BranchEditResponse)
def create_edit_branch(
    beat_id: BeatId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """S-BEAT7 entry — branches a proposed version. Autosave and outlet edits reuse the same
    `/draft` and `/draft/outlets` endpoints as the creation wizard (`beat.draft_version_id` points
    at whichever version is currently being worked on)."""

    return BeatService(session).create_edit_branch(claims=claims, beat_id=beat_id)


@router.post(
    "/beats/{beat_id}/edit-requests/submit",
    response_model=schemas.BeatDetailResponse,
    status_code=202,
    responses={200: {"model": schemas.BeatDetailResponse, "description": "Applied on submit"}},
)
def submit_edit(
    beat_id: BeatId,
    request: HttpRequest,
    raw_body: RawBody,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Transition #9 (S-BEAT7 "Send for approval") — `202` when it enters the approval queue,
    `200` when an Admin or Manager submits an edit to their own beat and it applies straight away
    (R-BEAT-17)."""

    status_code, payload = BeatService(session).submit_edit(
        claims=claims, beat_id=beat_id, idempotency_key=idempotency_key,
        raw_body=raw_body, request_id=get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.patch("/beats/{beat_id}", response_model=schemas.BeatDetailResponse)
def admin_update_beat(
    beat_id: BeatId,
    body: schemas.AdminUpdateBeatBody,
    raw_body: RawBody,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Immediate edit, no approval (R-BEAT-17) — S-BEAT6 edit form. Admin may edit any beat;
    a Manager may do the same for beats owned by Sales Persons in their own tree. Owner
    reassignment stays Admin-only."""

    return BeatService(session).admin_update_beat(
        claims=claims, beat_id=beat_id, body=body, idempotency_key=idempotency_key,
        raw_body=raw_body,
    )


@router.post("/beats/{beat_id}/deactivate", response_model=schemas.BeatDetailResponse)
def deactivate_beat(
    beat_id: BeatId,
    body: schemas.DeactivateBody,
    raw_body: RawBody,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Transition #13 (S-BEAT6 "Deactivate") — Admin-only, like reactivate (R-BEAT-21)."""

    return BeatService(session).deactivate(
        claims=claims, beat_id=beat_id, body=body, idempotency_key=idempotency_key,
        raw_body=raw_body,
    )


@router.post("/beats/{beat_id}/reactivate", response_model=schemas.BeatDetailResponse)
def reactivate_beat(
    beat_id: BeatId,
    raw_body: RawBody,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Transition #14 (S-BEAT6 "Reactivate")."""

    return BeatService(session).reactivate(
        claims=claims, beat_id=beat_id, idempotency_key=idempotency_key, raw_body=raw_body,
    )
