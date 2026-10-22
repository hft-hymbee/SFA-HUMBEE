"""Idempotency record helpers.

`claim` before `get` is what makes the pair safe under concurrency; see its docstring.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from humbee_sfa.platform.models import IdempotencyRecord


class IdempotencyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self, *, tenant_id: str, endpoint: str, key: str) -> None:
        """Serialise every in-flight request carrying this key, before reading it.

        Without this the pair below is check-then-act: two concurrent requests with the same key
        both find no record, both run the handler, and both insert — the loser then violates
        `uq_platform_idempotency` at commit and the caller gets a 500 instead of the first
        request's answer. Worse than the 500, both handlers ran, so an upstream call made inside
        the transaction happened twice even though the loser's own writes rolled back.

        The lock is transaction-scoped: the loser blocks here until the winner commits or rolls
        back, and then — at READ COMMITTED — its `get` below sees the committed record and replays
        through the ordinary path. Postgres releases it automatically, so a crashed handler cannot
        strand a key the way a persisted `in_progress` claim row would.

        Callers must therefore hold one transaction across `claim`, `get` and `save`; a commit in
        between drops the lock and reopens the race.

        Contention is per key. Distinct keys hash apart and never wait on each other.

        Postgres-only, deliberately unguarded: `response_payload` is `JSONB`, so this table cannot
        exist on another engine anyway, and quietly skipping the lock elsewhere would leave the
        race in place while looking like it was handled.
        """

        digest = hashlib.blake2b(
            f"{tenant_id}\x00{endpoint}\x00{key}".encode(), digest_size=8
        ).digest()
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": int.from_bytes(digest, "big", signed=True)},
        )

    def get(self, *, tenant_id: str, endpoint: str, key: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.is_active.is_(True),
            or_(
                IdempotencyRecord.expires_at.is_(None),
                IdempotencyRecord.expires_at > func.now(),
            ),
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save(
        self,
        *,
        tenant_id: str,
        endpoint: str,
        key: str,
        request_fingerprint: str,
        response_fingerprint: str,
        status_code: int,
        response_payload: dict[str, Any],
        actor_employee_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> IdempotencyRecord:
        row = IdempotencyRecord(
            tenant_id=tenant_id,
            endpoint=endpoint,
            idempotency_key=key,
            request_fingerprint=request_fingerprint,
            response_fingerprint=response_fingerprint,
            status_code=status_code,
            response_payload=response_payload,
            created_by_employee_id=actor_employee_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        return row

    @staticmethod
    def is_exact_replay(record: IdempotencyRecord, request_fingerprint: str) -> bool:
        return record.request_fingerprint == request_fingerprint
