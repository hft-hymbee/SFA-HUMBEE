from __future__ import annotations

from humbee_sfa.core.db import Base

REQUIRED_COLUMNS = {
    "id",
    "tenant_id",
    "created_at",
    "updated_at",
    "created_by_employee_id",
    "on_behalf_of_employee_id",
    "is_active",
    "deactivated_at",
    "deactivated_by",
}


def _is_exempt(table_name: str) -> bool:
    return (
        table_name == "alembic_version"
        or table_name.startswith(("fact_", "dim_"))
        or table_name == "reporting_projector_offset"
    )


def test_all_baseline_tables_follow_schema_conventions() -> None:
    missing_by_table = {
        table_name: missing
        for table_name, table in Base.metadata.tables.items()
        if not _is_exempt(table_name)
        and (missing := REQUIRED_COLUMNS - {column.name for column in table.columns})
    }
    assert missing_by_table == {}
