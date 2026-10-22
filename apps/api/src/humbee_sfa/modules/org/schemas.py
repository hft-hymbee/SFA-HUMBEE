"""Org HTTP request and response DTOs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

ROLE_CODES = ("sales_person", "manager", "admin")
STATUS_CODES = ("active", "inactive")

# Job-title axis, separate from ROLE_CODES (permission/hierarchy) — used for employee-report
# filtering. Each role only carries its own designations (`org_employees.designation_role_chk`).
DESIGNATIONS_BY_ROLE: dict[str, tuple[str, ...]] = {
    "admin": ("admin",),
    "manager": (
        "national_sales_head",
        "segment_business_head",
        "regional_sales_manager",
        "area_sales_manager",
    ),
    "sales_person": (
        "network_officer_salesperson",
        "territory_development_officer_salesperson",
    ),
}
DESIGNATION_CODES = tuple(code for codes in DESIGNATIONS_BY_ROLE.values() for code in codes)
_DESIGNATION_PATTERN = rf"^({'|'.join(DESIGNATION_CODES)})$"


class EmployeeResponse(BaseModel):
    id: str
    employee_code: str
    full_name: str
    first_name: str
    display_initials: str
    role_code: str
    designation_code: str
    status: str
    login_enabled: bool
    manager_employee_id: str | None
    joined_on: date | None
    phone_e164: str
    depth: int | None = None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int


class CreateEmployeeBody(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    role_code: str = Field(pattern=r"^(sales_person|manager|admin)$")
    designation_code: str = Field(pattern=_DESIGNATION_PATTERN)
    manager_employee_id: str | None = None
    login_enabled: bool = True
    joined_on: date | None = None
    privileged_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    casual_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    sick_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)


class CreateAdminBody(BaseModel):
    """Bootstrap-only payload: role and hierarchy fields are intentionally fixed."""

    employee_code: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    login_enabled: bool = True
    joined_on: date | None = None
    privileged_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    casual_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)
    sick_leave_days: Decimal | None = Field(default=None, ge=0, max_digits=4, decimal_places=1)


class UpdateEmployeeBody(BaseModel):
    """Every field optional — only supplied fields are applied."""

    employee_code: str | None = Field(default=None, min_length=1, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role_code: str | None = Field(default=None, pattern=r"^(sales_person|manager|admin)$")
    designation_code: str | None = Field(default=None, pattern=_DESIGNATION_PATTERN)
    login_enabled: bool | None = None
    joined_on: date | None = None


class MoveEmployeeBody(BaseModel):
    # `null` means "— Top level —".
    new_manager_employee_id: str | None = None


class DeactivateEmployeeBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class MoveCandidateResponse(BaseModel):
    id: str
    full_name: str
    role_code: str


class MoveCandidateListResponse(BaseModel):
    items: list[MoveCandidateResponse]


class TreeNodeResponse(BaseModel):
    id: str
    full_name: str
    role_code: str
    designation_code: str
    status: str
    depth: int
    is_actor: bool
    has_children: bool
    children: list[TreeNodeResponse]


class TreeResponse(BaseModel):
    roots: list[TreeNodeResponse]
