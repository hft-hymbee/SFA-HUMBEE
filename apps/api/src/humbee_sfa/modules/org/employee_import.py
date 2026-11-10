"""CSV parsing for the Admin bulk employee import. Pure: no session, no database.

The service owns everything that needs the database (duplicates against existing rows, resolving a
manager who already exists, the insert itself); this module turns bytes into validated
`CreateEmployeeBody` rows plus per-row errors, and orders rows so managers are written first.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.org import schemas

MAX_ROWS = 500
MAX_BYTES = 1_048_576

REQUIRED_COLUMNS = (
    "employee_code",
    "full_name",
    "phone",
    "role_code",
    "designation_code",
    "manager_code",
)
OPTIONAL_COLUMNS = (
    "login_enabled",
    "joined_on",
    "privileged_leave_days",
    "casual_leave_days",
    "sick_leave_days",
)
# Admins are a deliberate one-off (they hold no position in the tree), never a bulk row.
IMPORTABLE_ROLES = ("manager", "sales_person")

TEMPLATE_CSV = (
    ",".join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    + "\r\n"
    + "MGR-0001,Asha Rao,9876500001,manager,area_sales_manager,,true,2026-11-01,,,\r\n"
    + "SP-0001,Ravi Kumar,9876500002,sales_person,network_officer_salesperson,MGR-0001,"
    + "true,2026-11-01,,,\r\n"
)

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_PHONE_NOISE = re.compile(r"[\s\-().]")
_TRUE = frozenset({"true", "yes", "y", "1"})
_FALSE = frozenset({"false", "no", "n", "0"})
# `CreateEmployeeBody` field -> CSV column, for errors pydantic reports by field name.
_FIELD_COLUMNS = {"phone_e164": "phone"}


@dataclass(frozen=True)
class RowError:
    row: int
    column: str | None
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"row": self.row, "column": self.column, "code": self.code, "message": self.message}


@dataclass
class ParsedRow:
    """One data row. `body` is None when the row failed field validation; the raw identity fields
    are still kept so cross-row checks (duplicates, manager links) can run on every row."""

    row: int
    employee_code: str
    full_name: str
    role_code: str
    phone: str | None
    manager_code: str | None
    body: schemas.CreateEmployeeBody | None


def normalize_phone(raw: str) -> str | None:
    """`9876543210`, `919876543210` and `+919876543210` -> `+919876543210`; other E.164 passes
    through. Returns None when the value cannot be read as a phone number."""

    value = _PHONE_NOISE.sub("", raw)
    if value.startswith("+"):
        candidate = value
    elif value.isdigit() and len(value) == 10:
        candidate = f"+91{value}"
    elif value.isdigit() and len(value) == 12 and value.startswith("91"):
        candidate = f"+{value}"
    else:
        return None
    return candidate if _E164.match(candidate) else None


def parse_csv(data: bytes) -> tuple[list[ParsedRow], list[RowError]]:
    """File-level problems raise `ApiError`; row-level problems are returned so the caller can
    report every one of them at once."""

    if not data.strip():
        raise ApiError(422, "csv_empty", "The CSV file is empty.")
    try:
        text = data.decode("utf-8-sig")  # `-sig` drops the BOM Excel writes.
    except UnicodeDecodeError as exc:
        raise ApiError(422, "csv_invalid_encoding", "The CSV file must be UTF-8 encoded.") from exc

    reader = csv.reader(io.StringIO(text, newline=""))
    header = [column.strip().lower() for column in next(reader, [])]
    _check_header(header)

    records: list[tuple[int, dict[str, str]]] = []
    errors: list[RowError] = []
    for values in reader:
        if not any(value.strip() for value in values):
            continue
        if len(records) == MAX_ROWS:
            raise ApiError(
                422,
                "csv_too_many_rows",
                f"The CSV file has more than {MAX_ROWS} rows.",
                details={"max_rows": MAX_ROWS},
            )
        if len(values) > len(header):
            errors.append(
                RowError(
                    reader.line_num, None, "too_many_values", "Row has more values than columns."
                )
            )
        cells = {
            column: (values[i].strip() if i < len(values) else "")
            for i, column in enumerate(header)
        }
        records.append((reader.line_num, cells))
    if not records:
        raise ApiError(422, "csv_empty", "The CSV file has no data rows.")

    rows = []
    for line, cells in records:
        row, row_errors = _parse_row(line, cells)
        rows.append(row)
        errors.extend(row_errors)
    return rows, errors


def order_managers_first(rows: list[ParsedRow]) -> tuple[list[ParsedRow], list[RowError]]:
    """Order rows so an in-file manager is always written before its reports, and flag rows
    whose in-file manager chain loops back on itself."""

    by_code = {row.employee_code: row for row in rows if row.employee_code}
    depths: dict[int, int] = {}
    errors: list[RowError] = []
    for row in rows:
        seen = {row.employee_code}
        depth, current = 0, row
        if row.manager_code == row.employee_code:  # reported as `self_manager` by the row parser
            depths[row.row] = depth
            continue
        # ponytail: walks each chain from scratch, O(rows x depth); fine for 500 rows.
        while current.manager_code in by_code:
            if current.manager_code in seen:
                errors.append(
                    RowError(
                        row.row,
                        "manager_code",
                        "manager_cycle",
                        "The manager chain loops back on itself.",
                    )
                )
                break
            seen.add(current.manager_code)
            current = by_code[current.manager_code]
            depth += 1
        depths[row.row] = depth
    return sorted(rows, key=lambda row: depths[row.row]), errors


def _check_header(header: list[str]) -> None:
    if not header:
        raise ApiError(422, "csv_empty", "The CSV file has no header row.")
    duplicated = sorted({column for column in header if header.count(column) > 1})
    if duplicated:
        raise ApiError(
            422,
            "csv_duplicate_columns",
            "The CSV header repeats a column.",
            details={"columns": duplicated},
        )
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ApiError(
            422,
            "csv_missing_columns",
            "The CSV header is missing required columns.",
            details={"columns": missing},
        )
    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    unknown = [column for column in header if column not in known]
    if unknown:
        raise ApiError(
            422,
            "csv_unknown_columns",
            "The CSV header has columns this import does not accept.",
            details={"columns": unknown, "allowed": list(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)},
        )


def _parse_row(line: int, cells: dict[str, str]) -> tuple[ParsedRow, list[RowError]]:
    errors: list[RowError] = []

    phone = normalize_phone(cells["phone"]) if cells["phone"] else None
    if phone is None:
        errors.append(
            RowError(line, "phone", "invalid_phone", "Phone is missing or not a valid number.")
        )
    manager_code = cells["manager_code"] or None
    if manager_code is not None and manager_code == cells["employee_code"]:
        errors.append(
            RowError(line, "manager_code", "self_manager", "An employee cannot manage themselves.")
        )

    role_code = cells["role_code"]
    if role_code == "admin":
        errors.append(
            RowError(
                line, "role_code", "role_not_allowed", "Admins cannot be created by CSV import."
            )
        )

    fields: dict[str, Any] = {
        "employee_code": cells["employee_code"],
        "full_name": cells["full_name"],
        "phone_e164": phone or cells["phone"],
        "role_code": role_code,
        "designation_code": cells["designation_code"],
    }
    login_enabled = cells.get("login_enabled", "").lower()
    if login_enabled in _TRUE:
        fields["login_enabled"] = True
    elif login_enabled in _FALSE:
        fields["login_enabled"] = False
    elif login_enabled:
        errors.append(RowError(line, "login_enabled", "invalid_value", "Use true or false."))
    for column in ("joined_on", "privileged_leave_days", "casual_leave_days", "sick_leave_days"):
        if cells.get(column):
            fields[column] = cells[column]

    body = None
    try:
        body = schemas.CreateEmployeeBody(**fields)
    except ValidationError as exc:
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else None
            column = _FIELD_COLUMNS.get(field, field) if field else None
            if column == "phone" and phone is None:
                continue  # already reported as invalid_phone
            errors.append(RowError(line, column, "invalid_value", error["msg"]))
    if errors:
        body = None

    row = ParsedRow(
        row=line,
        employee_code=cells["employee_code"],
        full_name=cells["full_name"],
        role_code=role_code,
        phone=phone,
        manager_code=manager_code,
        body=body,
    )
    return row, errors
