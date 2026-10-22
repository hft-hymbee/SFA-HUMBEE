"""Audit log writer helper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from humbee_sfa.platform.models import AuditLog


class AuditLogService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_transition(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        from_state: str | None,
        to_state: str,
        actor_employee_id: str | None,
        reason: str | None = None,
        request_id: str | None = None,
        change_payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        row = AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            request_id=request_id,
            change_payload=change_payload,
            created_by_employee_id=actor_employee_id,
        )
        self._session.add(row)
        return row
