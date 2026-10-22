"""Provider-neutral port for Humbee's target-manufacturer roster (M13 §3.2/§3a).

`GET /sfa/v1/targets/manufacturers` is purpose-built for target setting: unlike
`/sfa/v1/manufacturer-roles` (onboarding role assignment, `onboarding.py`), it carries each
manufacturer's fixed target unit — `QUANTITY` (a volume, e.g. Ton) or `INR` (an amount, ₹). That
unit is Humbee's, not a per-target choice, so a sales target's basis is resolved per manufacturer
line from this roster rather than picked once for the whole target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from humbee_sfa.core.settings import Settings
from humbee_sfa.integration.humbee.client import HumbeeError, get_humbee_client

_TARGET_MEASURES = {
    ("QUANTITY", "Ton"): ("volume", "Ton"),
    ("INR", "₹"): ("amount", "₹"),
}


@dataclass(frozen=True)
class TargetManufacturer:
    manufacturer_id: str
    name: str
    basis: str
    uom_label: str


class TargetManufacturerMasterUnavailable(RuntimeError):
    """The target-manufacturer roster could not be read."""

    def __init__(self, message: str, *, corr_id: str | None = None) -> None:
        super().__init__(message)
        self.corr_id = corr_id


class HumbeeTargetManufacturerProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = get_humbee_client(settings)

    def list_manufacturers(self) -> list[TargetManufacturer]:
        try:
            data = self._client.call(
                "targets.manufacturers",
                "GET",
                "/sfa/v1/targets/manufacturers",
                route="/targets/manufacturers",
                timeout_s=3.0,
            )
            return [_manufacturer(item) for item in data]
        except HumbeeError as exc:
            raise TargetManufacturerMasterUnavailable(str(exc), corr_id=exc.corr_id) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise TargetManufacturerMasterUnavailable(
                f"unexpected target-manufacturer response shape: {exc}"
            ) from exc


def _manufacturer(item: dict[str, Any]) -> TargetManufacturer:
    uom = item["target_uom"]
    measure = (uom["uom_type"], uom["uom"])
    if measure not in _TARGET_MEASURES:
        raise ValueError(f"unsupported target_uom pair: {measure[0]} + {measure[1]}")
    basis, uom_label = _TARGET_MEASURES[measure]
    return TargetManufacturer(
        manufacturer_id=str(item["manufacturer_id"]),
        name=str(item["manufacturer_name"]),
        basis=basis,
        uom_label=uom_label,
    )


__all__ = [
    "HumbeeTargetManufacturerProvider",
    "TargetManufacturer",
    "TargetManufacturerMasterUnavailable",
]
