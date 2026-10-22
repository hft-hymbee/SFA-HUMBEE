"""Monthly RANGE-partition maintenance. database-design.md §17.1.

A missing partition is an insert failure, so this job keeps a rolling horizon of monthly
partitions provisioned ahead of first use. Partitioned tables are discovered from the Postgres
catalog (`pg_partitioned_table`) rather than a hardcoded list, so a table declared with
`postgresql_partition_by` in its ORM model is picked up automatically. Only single-column,
`date`-typed range partition keys are supported today — that is the only shape in current use
(`fact_employee_day` and its two bridge tables); a table partitioned on any other key shape is
logged and skipped rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = structlog.get_logger("humbee_sfa.platform.partition_maintenance")

# "Creates the next three months' partitions" (target-architecture.md §3): kept as a rolling
# horizon of the current month plus the next three, so the current month is always covered even
# if a run is missed.
PARTITION_HORIZON_MONTHS = 3

_PARTITION_SUFFIX_RE = re.compile(r"_p(\d{6})$")

_DISCOVER_PARTITIONED_TABLES_SQL = text(
    """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           a.attname AS column_name,
           format_type(a.atttypid, a.atttypmod) AS column_type
    FROM pg_partitioned_table pt
    JOIN pg_class c ON c.oid = pt.partrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    -- partattrs is int2vector, which (unlike a regular array) is 0-indexed.
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = pt.partattrs[0]
    WHERE pt.partstrat = 'r'
      AND array_length(pt.partattrs, 1) = 1
      AND n.nspname = ANY (current_schemas(false))
    """
)

_EXISTING_PARTITIONS_SQL = text(
    """
    SELECT child.relname
    FROM pg_inherits i
    JOIN pg_class child ON child.oid = i.inhrelid
    JOIN pg_class parent ON parent.oid = i.inhparent
    JOIN pg_namespace n ON n.oid = parent.relnamespace
    WHERE parent.relname = :table_name AND n.nspname = :schema_name
    """
)


@dataclass(frozen=True)
class PartitionedTable:
    schema_name: str
    table_name: str
    column_name: str


def _add_months(day: date, months: int) -> date:
    total_months = day.year * 12 + (day.month - 1) + months
    year, month0 = divmod(total_months, 12)
    return date(year, month0 + 1, 1)


def _discover_monthly_date_partitioned_tables(connection: Connection) -> list[PartitionedTable]:
    tables: list[PartitionedTable] = []
    for row in connection.execute(_DISCOVER_PARTITIONED_TABLES_SQL):
        if row.column_type != "date":
            logger.warning(
                "partition_maintenance_skipped_unsupported_key",
                table=row.table_name,
                column=row.column_name,
                column_type=row.column_type,
            )
            continue
        tables.append(PartitionedTable(row.schema_name, row.table_name, row.column_name))
    return tables


def _existing_partition_months(connection: Connection, table: PartitionedTable) -> set[date]:
    rows = connection.execute(
        _EXISTING_PARTITIONS_SQL,
        {"table_name": table.table_name, "schema_name": table.schema_name},
    )
    months: set[date] = set()
    for row in rows:
        match = _PARTITION_SUFFIX_RE.search(row.relname)
        if match is None:
            continue
        yyyymm = match.group(1)
        months.add(date(int(yyyymm[:4]), int(yyyymm[4:6]), 1))
    return months


def _ensure_partitions(
    connection: Connection,
    table: PartitionedTable,
    *,
    today: date,
    horizon_months: int,
) -> int:
    preparer = connection.dialect.identifier_preparer
    existing_months = _existing_partition_months(connection, table)
    qualified_parent = f"{preparer.quote(table.schema_name)}.{preparer.quote(table.table_name)}"

    current_month_start = date(today.year, today.month, 1)
    created = 0
    for offset in range(horizon_months + 1):
        period_start = _add_months(current_month_start, offset)
        if period_start in existing_months:
            continue
        period_end = _add_months(current_month_start, offset + 1)
        partition_name = f"{table.table_name}_p{period_start:%Y%m}"
        qualified_child = f"{preparer.quote(table.schema_name)}.{preparer.quote(partition_name)}"

        connection.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {qualified_child} "
                f"PARTITION OF {qualified_parent} "
                f"FOR VALUES FROM ('{period_start.isoformat()}') TO ('{period_end.isoformat()}')"
            )
        )
        created += 1
        logger.info(
            "partition_created",
            table=table.table_name,
            partition=partition_name,
            period_start=period_start.isoformat(),
        )
    return created


def run_partition_maintenance(
    connection: Connection,
    *,
    today: date,
    horizon_months: int = PARTITION_HORIZON_MONTHS,
) -> int:
    """Ensure every discovered monthly-partitioned table has partitions through the horizon.

    Returns the number of partitions created, used as the sweep run's `rows_affected`.
    """

    tables = _discover_monthly_date_partitioned_tables(connection)
    created = 0
    for table in tables:
        created += _ensure_partitions(connection, table, today=today, horizon_months=horizon_months)
    logger.info(
        "partition_maintenance_completed",
        tables_checked=len(tables),
        partitions_created=created,
    )
    return created
