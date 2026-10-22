"""Runtime configuration table/service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.platform.models import RuntimeConfig


class RuntimeConfigService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, tenant_id: str, key: str, default: Any = None) -> Any:
        stmt = select(RuntimeConfig).where(
            RuntimeConfig.tenant_id == tenant_id,
            RuntimeConfig.config_key == key,
            RuntimeConfig.is_active.is_(True),
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return default
        return row.config_value

    def upsert(
        self,
        *,
        tenant_id: str,
        key: str,
        value: dict[str, Any],
        actor_employee_id: str | None = None,
        description: str | None = None,
        config_type: str = "json",
    ) -> RuntimeConfig:
        stmt = select(RuntimeConfig).where(
            RuntimeConfig.tenant_id == tenant_id,
            RuntimeConfig.config_key == key,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = RuntimeConfig(
                tenant_id=tenant_id,
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=description,
                created_by_employee_id=actor_employee_id,
            )
            self._session.add(row)
            return row

        row.config_value = value
        row.config_type = config_type
        row.description = description
        return row
