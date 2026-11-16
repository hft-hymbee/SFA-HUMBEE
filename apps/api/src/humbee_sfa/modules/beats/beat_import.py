"""Excel parsing for the Admin bulk beat import. Pure: no session, no database, no Humbee.

The workbook has two sheets. "Beat Configuration" holds one beat per row; "Beat Outlets" lists
each beat's outlets by Humbee outlet id, joined back on Beat Name. This module turns the bytes into
`ParsedBeat`s plus every per-cell and cross-row error it can find on its own; the service owns
everything that needs the database or Humbee (owners, geography, outlet scope, taken outlets).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from openpyxl import Workbook, load_workbook

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.modules.beats import schemas

MAX_BEATS = 200
MAX_OUTLET_ROWS = 10_000
MAX_BYTES = 5 * 1_048_576
MAX_NAME_LENGTH = 64  # the name doubles as the beat code, `String(64)`

CONFIG_SHEET = "Beat Configuration"
OUTLETS_SHEET = "Beat Outlets"
# Key -> header as written in the template. Headers match ignoring case and spaces.
CONFIG_COLUMNS = {
    "name": "Beat Name",
    "employee_code": "Employee Code",
    "frequency": "Frequency",
    "visit_days": "Visit Days",
    "week_cycle": "Week Cycle",
    "categories": "Categories",
    "zones": "C1 (Zones)",
    "states": "C2 (States)",
    "districts": "C3 (Districts)",
}
OUTLET_COLUMNS = {"name": "Beat Name", "outlet_ref": "Outlet HUMBEE Code"}

_DAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_FREQUENCIES = ("daily", "weekly", "fortnightly", "monthly")


@dataclass(frozen=True)
class RowError:
    sheet: str
    row: int
    column: str | None
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "column": self.column,
            "code": self.code,
            "message": self.message,
        }


@dataclass
class ParsedBeat:
    """One "Beat Configuration" row. `frequency` is None when the cells could not be read; the
    service applies the wizard's completeness rules to the rest."""

    row: int
    name: str
    employee_code: str
    frequency: schemas.Frequency | None
    cats: list[str]
    zones: list[str]
    states: list[str]
    districts: list[str]
    outlet_refs: list[str] = field(default_factory=list)
    # outlet ref -> its "Beat Outlets" row, so outlet errors point at the right line.
    outlet_rows: dict[str, int] = field(default_factory=dict)


def parse_workbook(data: bytes) -> tuple[list[ParsedBeat], int, list[RowError]]:
    """Returns the beats, the outlet row count, and every row-level error. File-level problems
    raise `ApiError`."""

    if len(data) > MAX_BYTES:
        raise ApiError(
            413,
            "file_too_large",
            "The Excel file is larger than 5 MB.",
            details={"max_bytes": MAX_BYTES},
        )
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises zip, XML and key errors for a non-workbook
        raise ApiError(422, "xlsx_invalid", "The file is not a readable .xlsx workbook.") from exc
    try:
        config = _read_sheet(workbook, CONFIG_SHEET, CONFIG_COLUMNS, MAX_BEATS)
        outlets = _read_sheet(workbook, OUTLETS_SHEET, OUTLET_COLUMNS, MAX_OUTLET_ROWS)
    finally:
        workbook.close()
    if not config:
        raise ApiError(422, "xlsx_empty", f'The "{CONFIG_SHEET}" sheet has no beats.')

    errors: list[RowError] = []
    beats: list[ParsedBeat] = []
    by_name: dict[str, ParsedBeat] = {}
    for line, cells in config:
        beat, row_errors = _parse_beat(line, cells)
        errors.extend(row_errors)
        key = beat.name.lower()
        if key and key in by_name:
            errors.append(
                _config_error(
                    line, "name", "duplicate_in_file", f"Same Beat Name as row {by_name[key].row}."
                )
            )
            continue
        if key:
            by_name[key] = beat
        beats.append(beat)

    holder: dict[str, ParsedBeat] = {}  # outlet ref -> the beat that listed it first
    for line, cells in outlets:
        name, ref = cells["name"], cells["outlet_ref"]
        if not name or not ref:
            column = "name" if not name else "outlet_ref"
            errors.append(
                _outlet_error(line, column, "invalid_value", f"{OUTLET_COLUMNS[column]} is required.")
            )
            continue
        beat = by_name.get(name.lower())
        if beat is None:
            errors.append(
                _outlet_error(
                    line, "name", "unknown_beat", f'No beat named "{name}" in "{CONFIG_SHEET}".'
                )
            )
            continue
        first = holder.get(ref)
        if first is not None:
            where = "this beat" if first is beat else f'beat "{first.name}"'
            errors.append(
                _outlet_error(
                    line,
                    "outlet_ref",
                    "duplicate_in_file",
                    f"Already listed under {where} (row {first.outlet_rows[ref]}).",
                )
            )
            continue
        holder[ref] = beat
        beat.outlet_refs.append(ref)
        beat.outlet_rows[ref] = line

    for beat in beats:
        if beat.name and not beat.outlet_refs:
            errors.append(
                _config_error(
                    beat.row,
                    "name",
                    "no_outlets_selected",
                    f'No outlets listed for this beat in "{OUTLETS_SHEET}".',
                )
            )
    return beats, len(outlets), errors


def template_xlsx() -> bytes:
    workbook = Workbook()
    config = workbook.active
    assert config is not None
    config.title = CONFIG_SHEET
    config.append(list(CONFIG_COLUMNS.values()))
    config.append(["Indiranagar Mon-Thu", "SP-0001", "weekly", "Mon, Thu", "", "", "1", "10", "100"])
    config.append(
        ["Mysuru Fortnightly", "SP-0001", "fortnightly", "Tue", "1, 3", "CATEGORY_A", "1", "10", "101"]
    )
    outlets = workbook.create_sheet(OUTLETS_SHEET)
    outlets.append(list(OUTLET_COLUMNS.values()))
    for name, ref in (
        ("Indiranagar Mon-Thu", "1001"),
        ("Indiranagar Mon-Thu", "1002"),
        ("Mysuru Fortnightly", "2001"),
    ):
        outlets.append([name, ref])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _read_sheet(
    workbook: Any, title: str, columns: dict[str, str], max_rows: int
) -> list[tuple[int, dict[str, str]]]:
    if title not in workbook.sheetnames:
        raise ApiError(
            422,
            "xlsx_missing_sheet",
            f'The workbook has no "{title}" sheet.',
            details={"sheet": title, "sheets": list(workbook.sheetnames)},
        )
    rows = workbook[title].iter_rows(values_only=True)
    header = [_normalise_header(value) for value in next(rows, ())]
    while header and not header[-1]:
        header.pop()  # trailing empty cells Excel leaves behind
    _check_header(title, header, columns)
    key_by_header = {_normalise_header(label): key for key, label in columns.items()}
    keys = [key_by_header[value] for value in header]

    records: list[tuple[int, dict[str, str]]] = []
    for line, values in enumerate(rows, start=2):
        cells = [_cell(value) for value in values[: len(keys)]]
        if not any(cells):
            continue
        if len(records) == max_rows:
            raise ApiError(
                422,
                "xlsx_too_many_rows",
                f'The "{title}" sheet has more than {max_rows} rows.',
                details={"sheet": title, "max_rows": max_rows},
            )
        cells += [""] * (len(keys) - len(cells))
        records.append((line, dict(zip(keys, cells, strict=True))))
    return records


def _check_header(title: str, header: list[str], columns: dict[str, str]) -> None:
    if not header:
        raise ApiError(422, "xlsx_empty", f'The "{title}" sheet has no header row.')
    known = {_normalise_header(label): label for label in columns.values()}
    duplicated = sorted({value for value in header if value and header.count(value) > 1})
    if duplicated:
        raise ApiError(
            422,
            "xlsx_duplicate_columns",
            f'The "{title}" header repeats a column.',
            details={"sheet": title, "columns": duplicated},
        )
    missing = [label for value, label in known.items() if value not in header]
    if missing:
        raise ApiError(
            422,
            "xlsx_missing_columns",
            f'The "{title}" header is missing required columns.',
            details={"sheet": title, "columns": missing},
        )
    unknown = [value for value in header if value not in known]
    if unknown:
        raise ApiError(
            422,
            "xlsx_unknown_columns",
            f'The "{title}" header has columns this import does not accept.',
            details={"sheet": title, "columns": unknown, "allowed": list(columns.values())},
        )


def _parse_beat(line: int, cells: dict[str, str]) -> tuple[ParsedBeat, list[RowError]]:
    errors: list[RowError] = []
    name = cells["name"]
    if not name:
        errors.append(_config_error(line, "name", "invalid_value", "Beat Name is required."))
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(
            _config_error(
                line, "name", "invalid_value", f"Beat Name is longer than {MAX_NAME_LENGTH} characters."
            )
        )
    if not cells["employee_code"]:
        errors.append(
            _config_error(line, "employee_code", "invalid_value", "Employee Code is required.")
        )

    geo: dict[str, list[str]] = {}
    for level in ("zones", "states", "districts"):
        geo[level] = _split(cells[level])
        if not geo[level]:
            errors.append(
                _config_error(line, level, "invalid_value", f"{CONFIG_COLUMNS[level]} is required.")
            )

    cats = list(dict.fromkeys(value.upper() for value in _split(cells["categories"])))
    unknown_cats = [value for value in cats if value not in schemas.ShopCategory.__members__]
    if unknown_cats:
        errors.append(
            _config_error(
                line,
                "categories",
                "invalid_value",
                f"Unknown categories: {', '.join(unknown_cats)}. "
                f"Use {', '.join(schemas.ShopCategory.__members__)}.",
            )
        )
        # Reported above; dropping them keeps the outlet check from piling on a second error.
        cats = [value for value in cats if value not in unknown_cats]

    frequency, frequency_errors = _parse_frequency(line, cells)
    errors.extend(frequency_errors)
    beat = ParsedBeat(
        row=line,
        name=name,
        employee_code=cells["employee_code"],
        frequency=frequency,
        cats=cats,
        zones=geo["zones"],
        states=geo["states"],
        districts=geo["districts"],
    )
    return beat, errors


def _parse_frequency(
    line: int, cells: dict[str, str]
) -> tuple[schemas.Frequency | None, list[RowError]]:
    errors: list[RowError] = []
    frequency = cells["frequency"].lower()
    if frequency not in _FREQUENCIES:
        errors.append(
            _config_error(
                line, "frequency", "invalid_value", f"Use one of: {', '.join(_FREQUENCIES)}."
            )
        )
    visit_days: list[int] = []
    for value in _split(cells["visit_days"]):
        day = _DAYS.get(value.lower()[:3])
        if day is None:
            errors.append(
                _config_error(
                    line, "visit_days", "invalid_value", f'"{value}" is not a day; use Mon, Tue, …'
                )
            )
        elif day not in visit_days:
            visit_days.append(day)
    week_cycle: list[int] = []
    for value in _split(cells["week_cycle"]):
        if value not in ("1", "2", "3", "4"):
            errors.append(
                _config_error(line, "week_cycle", "invalid_value", f'"{value}" is not a week 1-4.')
            )
        elif int(value) not in week_cycle:
            week_cycle.append(int(value))
    if errors:
        return None, errors
    return (
        schemas.Frequency(frequency=frequency, visit_days=visit_days, week_cycle=week_cycle),  # type: ignore[arg-type]
        [],
    )


def _cell(value: Any) -> str:
    """Excel stores typed ids as numbers: `100.0` must read as `"100"`."""

    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _split(value: str) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def _normalise_header(value: Any) -> str:
    return "".join(str(value or "").split()).lower()


def _config_error(line: int, key: str, code: str, message: str) -> RowError:
    return RowError(CONFIG_SHEET, line, CONFIG_COLUMNS[key], code, message)


def _outlet_error(line: int, key: str, code: str, message: str) -> RowError:
    return RowError(OUTLETS_SHEET, line, OUTLET_COLUMNS[key], code, message)
