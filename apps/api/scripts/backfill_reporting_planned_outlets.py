"""Backfill route-day facts in `fact_employee_day` for days recorded before the day model.

The fold reads `planned`, `visit_type` and `checked_in_at` from `visit_completed`. This script
publishes the missing `route_plan_saved` event for every plan that has stops but never published
one (beat starts before the fix), and recomputes every affected employee-day from the event log
(M11 §3b.3 rule 2). Re-running converges on the same rows. `last_event_at` is left untouched: a backfill is not folding an event (see
`upsert_fact_employee_day`).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, inspect, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import humbee_sfa.models_registry  # noqa: F401
from humbee_sfa.core.db import get_engine, get_sessionmaker, transaction
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.reporting.producers.routes_rollup import (
    ROUTE_PLAN_SAVED,
    STREAM,
    VISIT_COMPLETED,
    recompute_employee_day,
)
from humbee_sfa.modules.routes.models.route_plan import RoutePlan
from humbee_sfa.modules.routes.models.route_stop import RouteStop
from humbee_sfa.platform.domain_events import DomainEventPublisher
from humbee_sfa.platform.models import DomainEvent


def main() -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    required_tables = {"platform_domain_events", "fact_employee_day"}
    missing_tables = sorted(required_tables - set(inspect(engine).get_table_names()))
    if missing_tables:
        raise RuntimeError(f"Missing tables: {missing_tables}")

    tenant_id = settings.tenant_id
    session_factory = get_sessionmaker(settings.database_url)
    folded = 0
    errors = 0
    with session_factory() as session:
        with transaction(session):
            published_plan_ids = select(DomainEvent.aggregate_id).where(
                DomainEvent.tenant_id == tenant_id,
                DomainEvent.stream == STREAM,
                DomainEvent.event_type == ROUTE_PLAN_SAVED,
            )
            unpublished_plans = session.execute(
                select(RoutePlan, func.count(RouteStop.id))
                .join(RouteStop, RouteStop.route_plan_id == RoutePlan.id)
                .where(RoutePlan.tenant_id == tenant_id, RoutePlan.id.not_in(published_plan_ids))
                .group_by(RoutePlan.id)
            ).all()
            publisher = DomainEventPublisher(session)
            for plan, stop_count in unpublished_plans:
                publisher.publish(
                    tenant_id=tenant_id,
                    stream=STREAM,
                    event_type=ROUTE_PLAN_SAVED,
                    aggregate_type="route_plan",
                    aggregate_id=plan.id,
                    payload={
                        "employee_id": plan.employee_id,
                        "business_date": plan.business_date.isoformat(),
                        "beat_id": plan.beat_id,
                        "run_origin": "assigned_beat",
                        "stop_count": int(stop_count),
                    },
                    actor_employee_id=plan.created_by_employee_id,
                    occurred_at=plan.created_at,
                )
        rows = (
            session.execute(
                select(DomainEvent)
                .where(
                    DomainEvent.tenant_id == tenant_id,
                    DomainEvent.stream == STREAM,
                    DomainEvent.event_type.in_((ROUTE_PLAN_SAVED, VISIT_COMPLETED)),
                )
                .order_by(DomainEvent.event_seq)
            )
            .scalars()
            .all()
        )
        days = {
            (
                str(row.payload["employee_id"]),
                str(row.payload.get("business_date") or row.business_date.isoformat()),
            )
            for row in rows
            if row.payload.get("employee_id")
        }
        for employee_id, business_date in sorted(days):
            try:
                # One transaction per employee-day. Explicit exception to the one-transaction
                # rule: same reason as a projector per-item drain — a failure must not lose
                # prior days so the operator can resume.
                with transaction(session):
                    recompute_employee_day(
                        session,
                        tenant_id=tenant_id,
                        employee_id=employee_id,
                        business_date=date.fromisoformat(business_date),
                    )
                folded += 1
            except Exception as exc:  # noqa: BLE001 - resume-safe: count and continue
                errors += 1
                print(
                    f"error employee_id={employee_id} business_date={business_date} "
                    f"{type(exc).__name__}: {exc}"
                )

    print(f"days_folded={folded} errors={errors}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()