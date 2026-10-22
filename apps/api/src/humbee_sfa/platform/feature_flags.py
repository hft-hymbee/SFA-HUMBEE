"""Feature flag storage and evaluation helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from humbee_sfa.platform.models import FeatureFlag


class FeatureFlagService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def set_flag(
        self,
        *,
        tenant_id: str,
        flag_key: str,
        enabled: bool,
        rollout_rules: dict[str, Any] | None = None,
        actor_employee_id: str | None = None,
        notes: str | None = None,
    ) -> FeatureFlag:
        stmt = select(FeatureFlag).where(FeatureFlag.tenant_id == tenant_id, FeatureFlag.flag_key == flag_key)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = FeatureFlag(
                tenant_id=tenant_id,
                flag_key=flag_key,
                enabled=enabled,
                rollout_rules=rollout_rules,
                notes=notes,
                created_by_employee_id=actor_employee_id,
            )
            self._session.add(row)
            return row

        row.enabled = enabled
        row.rollout_rules = rollout_rules
        row.notes = notes
        return row

    def is_enabled(
        self,
        *,
        tenant_id: str,
        flag_key: str,
        role: str | None = None,
        region: str | None = None,
    ) -> bool:
        stmt = select(FeatureFlag).where(
            FeatureFlag.tenant_id == tenant_id,
            FeatureFlag.flag_key == flag_key,
            FeatureFlag.is_active.is_(True),
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None or not row.enabled:
            return False
        if not row.rollout_rules:
            return True

        allowed_roles = row.rollout_rules.get("roles")
        if isinstance(allowed_roles, list) and role and role not in allowed_roles:
            return False

        allowed_regions = row.rollout_rules.get("regions")
        return not (isinstance(allowed_regions, list) and region and region not in allowed_regions)
