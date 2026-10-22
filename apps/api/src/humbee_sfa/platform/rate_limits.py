"""Rate-limit counter helper on Postgres/SQL tables (no Redis)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.platform.models import RateLimitCounter


class RateLimitService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def increment_and_check(
        self,
        *,
        tenant_id: str,
        scope: str,
        counter_key: str,
        window_start: datetime,
        window_seconds: int,
        max_hits: int,
        actor_employee_id: str | None = None,
    ) -> tuple[bool, int]:
        stmt = select(RateLimitCounter).where(
            RateLimitCounter.tenant_id == tenant_id,
            RateLimitCounter.scope == scope,
            RateLimitCounter.counter_key == counter_key,
            RateLimitCounter.window_start == window_start,
            RateLimitCounter.window_seconds == window_seconds,
            RateLimitCounter.is_active.is_(True),
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = RateLimitCounter(
                tenant_id=tenant_id,
                scope=scope,
                counter_key=counter_key,
                window_start=window_start,
                window_seconds=window_seconds,
                hit_count=0,
                created_by_employee_id=actor_employee_id,
            )
            self._session.add(row)

        row.hit_count = row.hit_count + 1
        return row.hit_count <= max_hits, row.hit_count
