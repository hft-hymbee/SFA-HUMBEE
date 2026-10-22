"""Today composition HTTP route."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from humbee_sfa.core.db import get_db_session
from humbee_sfa.core.deps import AccessTokenClaims, get_current_claims
from humbee_sfa.modules.home.schemas import TodayResponse
from humbee_sfa.modules.home.service import TodayService

router = APIRouter(prefix="/api/v1", tags=["Routes & Visits"])


@router.get("/home/today", response_model=TodayResponse)
def get_today(
    claims: Annotated[AccessTokenClaims, Depends(get_current_claims)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return TodayService(session).get_today(claims=claims)
