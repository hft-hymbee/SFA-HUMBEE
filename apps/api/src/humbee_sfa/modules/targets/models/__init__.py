"""`targets` models. Read this file for the index; open a specific module for column detail.

- `target.py`                          `Target` — `targets`, one active row per (employee, type,
  month); `target_value` is null for `sales` — the rollup is derived per-basis from its lines
  since a sales target has no single basis of its own.
- `target_manufacturer_line.py`        `TargetManufacturerLine` — `targets_manufacturer_lines`,
  per-manufacturer breakdown of a `sales` target; `line_basis` comes from that manufacturer's own
  Humbee-fixed unit, resolved server-side and snapshotted; declared FK `ON DELETE CASCADE` to `targets`.
- `lead.py`                            `Lead` — `targets_leads`, a captured prospect for manufacturers
  not on Humbee, named as free text.
"""

from __future__ import annotations

from humbee_sfa.modules.targets.models.lead import Lead
from humbee_sfa.modules.targets.models.target import Target
from humbee_sfa.modules.targets.models.target_manufacturer_line import TargetManufacturerLine

__all__ = [
    "Lead",
    "Target",
    "TargetManufacturerLine",
]
