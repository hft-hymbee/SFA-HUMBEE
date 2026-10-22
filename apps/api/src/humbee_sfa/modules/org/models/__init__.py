"""`org` models — database-design.md §4. Read this file for the index; open a specific module
for column detail.

- `employee.py`        Employee, HierarchyEdge`s parent — `org_employees`, the employee master.
- `hierarchy_edge.py`   `org_hierarchy_edges` — closure table, no depth cap (§19.8).
- `geography_scope_assignment.py`  `org_geography_scope_assignments` — per-employee territory,
  with an `{id, name}` label snapshot taken at assignment time. The four
  ACL-written geography master cache tables (`org_zone_clusters`, `org_state_clusters`,
  `org_district_clusters`, `org_shop_categories`) were retired in the same story — the master is
  now read live from Humbee, never cached.
"""

from __future__ import annotations

from humbee_sfa.modules.org.models.employee import Employee
from humbee_sfa.modules.org.models.geography_scope_assignment import GeographyScopeAssignment
from humbee_sfa.modules.org.models.hierarchy_edge import HierarchyEdge

__all__ = [
    "Employee",
    "GeographyScopeAssignment",
    "HierarchyEdge",
]
