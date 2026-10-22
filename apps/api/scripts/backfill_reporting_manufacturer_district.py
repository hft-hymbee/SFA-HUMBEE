"""Recompute FEMD rows and FEOD district stamps for every employee-day that has orders.

Idempotent: re-running the same day overwrites FEMD / FEOD order columns + district via the
same full-day recompute as the orders projector. No Humbee calls — district comes from the
local outlet projection.

Run it after `alembic upgrade head`; until it runs, manufacturer and district charts stay empty for
days recorded before the projector stamped districts.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import humbee_sfa.models_registry  # noqa: F401
from humbee_sfa.core.db import get_engine, get_sessionmaker, transaction
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.orders.service import (
    list_order_reporting_employee_days,
    list_order_reporting_fields_for_day,
)
from humbee_sfa.modules.reporting.producers.orders_rollup import fold_orders_for_employee_day


def main() -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    required_tables = {
        "orders",
        "fact_employee_day",
        "fact_employee_outlet_day",
        "fact_employee_manufacturer_day",
    }
    missing_tables = sorted(required_tables - set(inspect(engine).get_table_names()))
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            "Run `alembic upgrade head` from apps/api before this backfill. "
            f"Missing tables: {missing}"
        )

    tenant_id = settings.tenant_id
    session_factory = get_sessionmaker(settings.database_url)
    folded = 0
    errors = 0
    with session_factory() as session:
        days = list_order_reporting_employee_days(session, tenant_id=tenant_id)
        for employee_id, business_date in days:
            try:
                # One transaction per employee-day. Explicit exception to the one-transaction
                # rule: same reason as a projector per-item drain — a failure must not lose
                # prior days so the operator can resume.
                with transaction(session):
                    fold_orders_for_employee_day(
                        session,
                        tenant_id=tenant_id,
                        employee_id=employee_id,
                        business_date=business_date,
                        day_orders=list_order_reporting_fields_for_day(
                            session,
                            tenant_id=tenant_id,
                            employee_id=employee_id,
                            business_date=business_date,
                        ),
                        # Recompute from current order state, not an event fold — leave
                        # `fact_employee_day.last_event_at` at whatever the log last set.
                        last_event_at=None,
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
