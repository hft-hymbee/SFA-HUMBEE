from __future__ import annotations

import pytest
from sqlalchemy import Column, MetaData, String, Table

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
    """database-design.md §2.4 rule 2 / §3 reconciliation item 12: the star schema has composite
    natural keys and no actor columns, so `fact_*`, `dim_*` and `reporting_projector_offset`
    never carry the baseline conventions."""
    return (
        table_name.startswith("fact_")
        or table_name.startswith("dim_")
        or table_name == "reporting_projector_offset"
    )


def assert_schema_conventions(metadata: MetaData) -> None:
    missing_by_table: dict[str, set[str]] = {}

    for table_name, table in metadata.tables.items():
        if table_name == "alembic_version" or _is_exempt(table_name):
            continue
        available_columns = {column.name for column in table.columns}
        missing = REQUIRED_COLUMNS - available_columns
        if missing:
            missing_by_table[table_name] = missing

    assert not missing_by_table, f"Conventions missing: {missing_by_table}"


def test_all_baseline_tables_follow_schema_conventions() -> None:
    assert_schema_conventions(Base.metadata)


def test_convention_guard_fails_table_missing_required_columns() -> None:
    metadata = MetaData()
    Table("invalid_table", metadata, Column("id", String(26), primary_key=True))

    with pytest.raises(AssertionError):
        assert_schema_conventions(metadata)
