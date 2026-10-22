"""`reporting` models — the star schema. Read this file for the index; open a specific
module for column detail.

Whole-module exemption: every table here is EXEMPT from the naming and conventions rules
that every other module's tables follow via `ConventionsMixin` — no ULID `id`, no
`tenant_id`-via-mixin/timestamps/actor columns/soft-delete. Each table instead carries its own
explicit primary key (an identity surrogate for `dim_employee`, natural composite keys
elsewhere), because every table here is derived and droppable — the durable truth is
`platform_domain_events`, and these tables are rebuilt from it by the reporting projector.

- `dim_employee.py`                    `dim_employee` — SCD type 2 employee dimension.
- `fact_employee_day.py`               `fact_employee_day` — daily employee grain fact.
- `fact_employee_outlet_day.py`        `fact_employee_outlet_day` — daily employee x outlet fact.
- `fact_employee_manufacturer_day.py`  `fact_employee_manufacturer_day` — daily employee x manufacturer fact.
- `projector_offset.py`                `reporting_projector_offset` — projector checkpoint.

`dim_business_date`, `fact_employee_sku_day` and
`reporting_recompute_queue` were removed — no producer, service, or screen ever read or wrote
them.
"""

from __future__ import annotations

from humbee_sfa.modules.reporting.models.dim_employee import DimEmployee
from humbee_sfa.modules.reporting.models.fact_employee_day import FactEmployeeDay
from humbee_sfa.modules.reporting.models.fact_employee_manufacturer_day import (
    FactEmployeeManufacturerDay,
)
from humbee_sfa.modules.reporting.models.fact_employee_outlet_day import FactEmployeeOutletDay
from humbee_sfa.modules.reporting.models.projector_offset import ProjectorOffset

__all__ = [
    "DimEmployee",
    "FactEmployeeDay",
    "FactEmployeeManufacturerDay",
    "FactEmployeeOutletDay",
    "ProjectorOffset",
]
