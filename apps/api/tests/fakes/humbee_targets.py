from __future__ import annotations

from tests.fakes.humbee import FakeHumbee, HumbeeCall

UOM = {"amount": ("INR", "₹"), "volume": ("QUANTITY", "Ton")}


def install_target_manufacturers(fake: FakeHumbee, manufacturers: dict[str, tuple[str, str]]) -> None:
    def roster(call: HumbeeCall) -> list[dict[str, object]]:
        return [
            {
                "manufacturer_id": int(manufacturer_id),
                "manufacturer_name": name,
                "target_uom": {"uom_type": UOM[basis][0], "uom": UOM[basis][1]},
            }
            for manufacturer_id, (name, basis) in manufacturers.items()
        ]

    fake.route("GET", "/sfa/v1/targets/manufacturers")(roster)
