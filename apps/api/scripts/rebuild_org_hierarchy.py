"""Re-derive the org closure table and ltree paths from `manager_employee_id`.

Run this against a tenant whose managers see an empty team, whose org tree comes back empty, or
whose requests auto-approve instead of routing to a manager. All three are the same symptom:
`org_hierarchy_edges` disagreeing with the adjacency column that is the editable truth.
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
from humbee_sfa.core.db import get_engine, get_sessionmaker
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.org.service import rebuild_hierarchy


def main() -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    required_tables = {"org_employees", "org_hierarchy_edges"}
    missing_tables = sorted(required_tables - set(inspect(engine).get_table_names()))
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            "Schema is not migrated. Run `alembic upgrade head` from apps/api first. "
            f"Missing tables: {missing}"
        )

    session_factory = get_sessionmaker(settings.database_url)
    with session_factory() as session:
        members, edges = rebuild_hierarchy(session, tenant_id=settings.tenant_id)
        session.commit()

    print("Hierarchy rebuilt:")
    print(f"  tenant_id: {settings.tenant_id}")
    print(f"  tree members: {members}")
    print(f"  closure edges: {edges}")


if __name__ == "__main__":
    main()
