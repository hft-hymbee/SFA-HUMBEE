"""Orders/cart HTTP routes. Handlers translate HTTP only; transaction ownership and scope resolution live in `CartService`/`OrderService`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi import Request as HttpRequest
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.orders import schemas
from humbee_sfa.modules.orders.service import CartService, OrderService

router = APIRouter(prefix="/api/v1", tags=["Orders"])

CartId = Annotated[str, Path(min_length=1, max_length=26)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]
OrderManufacturerId = Annotated[
    str,
    Query(description="Humbee brand_id selected from outlet seller links; sent upstream as manufacturer_id."),
]


@router.post("/carts", response_model=schemas.CartResponse)
async def create_cart(
    body: schemas.CreateCartBody,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Creates or resumes the open cart for `(visit, outlet, manufacturer)`."""

    status_code, payload = CartService(session).create_or_get_cart(claims=claims, body=body)
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/carts/{cart_id}", response_model=schemas.CartResponse)
def get_cart(
    cart_id: CartId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Re-prices and re-evaluates the scheme on every read."""

    return CartService(session).get_cart(claims=claims, cart_id=cart_id)


@router.patch("/carts/{cart_id}", response_model=schemas.CartResponse)
async def patch_cart(
    cart_id: CartId,
    body: schemas.PatchCartBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Sets `source_po_id`, ship-to and the shipping-address override."""

    status_code, payload = CartService(session).patch_cart(
        claims=claims, cart_id=cart_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.put("/carts/{cart_id}/lines", response_model=schemas.CartResponse)
async def upsert_line(
    cart_id: CartId,
    body: schemas.UpsertLinesBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Cart line mutations. `qty = 0` removes the line."""

    status_code, payload = CartService(session).upsert_line(
        claims=claims, cart_id=cart_id, body=body, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/orders/context", response_model=schemas.OrderContextResponse)
def get_order_context(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    visit_id: Annotated[str, Query()],
    outlet_id: Annotated[str, Query()],
    manufacturer_id: OrderManufacturerId,
    seller_id: Annotated[str | None, Query()] = None,
    outlet_esi_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Fan-out: manufacturer + sellers + routing + POs + ship-to, one call."""

    return CartService(session).get_order_context(
        claims=claims,
        visit_id=visit_id,
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        seller_id=seller_id,
        outlet_esi_id=outlet_esi_id,
    )


@router.get("/orders/purchase-orders", response_model=schemas.PurchaseOrdersResponse)
def get_purchase_orders(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    outlet_id: Annotated[str, Query()],
    manufacturer_id: OrderManufacturerId,
    outlet_esi_id: Annotated[str, Query(min_length=1)],
) -> dict[str, Any]:
    """Open POs for `(outlet, manufacturer, outlet_esi_id)`, live, never cached."""

    return CartService(session).get_purchase_orders(
        claims=claims,
        outlet_id=outlet_id,
        manufacturer_id=manufacturer_id,
        outlet_esi_id=outlet_esi_id,
    )


@router.get("/orders/serviceable-states", response_model=schemas.ServiceableStatesResponse)
def get_serviceable_states(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    manufacturer_id: OrderManufacturerId,
) -> dict[str, Any]:
    """Bounds the shipping-address state dropdown to where this manufacturer delivers."""

    return CartService(session).list_serviceable_states(
        claims=claims, manufacturer_id=manufacturer_id
    )


@router.get("/orders/serviceable-districts", response_model=schemas.ServiceableDistrictsResponse)
def get_serviceable_districts(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    manufacturer_id: OrderManufacturerId,
    state_id: Annotated[str, Query()],
) -> dict[str, Any]:
    """Bounds the shipping-address district dropdown, once a state has been picked."""

    return CartService(session).list_serviceable_districts(
        claims=claims, manufacturer_id=manufacturer_id, state_id=state_id
    )


@router.get("/orders/catalog", response_model=schemas.CatalogResponse)
def get_catalog(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    cart_id: Annotated[str, Query()],
    q: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Products + prices + stock + cart quantity, merged."""

    return CartService(session).get_catalog(
        claims=claims, cart_id=cart_id, query=q, category=category
    )


@router.post("/orders", response_model=schemas.OrderDetailOut, status_code=202)
async def submit_order(
    body: schemas.SubmitOrderBody,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """A seller not requiring manager approval routes straight to `approved`; one
    that does opens a generic approval request."""

    status_code, payload = OrderService(session).submit_order(
        claims=claims, body=body, idempotency_key=idempotency_key, raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/orders", response_model=schemas.OrderListResponse)
def list_orders(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
    status: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    """SELF for a Sales Person, OWN_TREE for a Manager."""

    return OrderService(session).list_orders(
        claims=claims, status=status, cursor=cursor, limit=limit
    )


@router.get("/orders/{order_id}", response_model=schemas.OrderDetailOut)
def get_order(
    order_id: CartId,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Out-of-scope returns `404`, never `403`."""

    return OrderService(session).get_order(claims=claims, order_id=order_id)


@router.post("/orders/{order_id}/retry-submission", response_model=schemas.OrderDetailOut)
async def retry_submission(
    order_id: CartId,
    request: HttpRequest,
    idempotency_key: IdempotencyKey,
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> JSONResponse:
    """Retry submission — re-attempts registration only; approval is never re-requested."""

    status_code, payload = OrderService(session).retry_submission(
        claims=claims, order_id=order_id, idempotency_key=idempotency_key,
        raw_body=await request.body(),
    )
    return JSONResponse(status_code=status_code, content=payload)
