from __future__ import annotations

from typing import Any

from tests.fakes.humbee import AS_OF, FakeHumbee, HumbeeCall

COMPANY_ID_BASE = 9000
MANUFACTURER_ID = "M1"
FIRM_ROLE_ID = "R7"
LOCATION_ID = "5001"
PINCODE = "560001"


def install_onboarding(fake: FakeHumbee) -> None:
    @fake.route("GET", "/sfa/v1/verify/phone-number")
    def verify_phone(call: HumbeeCall) -> Any:
        return {"phone_number": call.params["phone_number"]}

    @fake.route("POST", "/sfa/v1/onboard")
    def onboard(call: HumbeeCall) -> Any:
        return {"company_id": COMPANY_ID_BASE + len(fake.calls_to("POST", "/sfa/v1/onboard"))}

    @fake.route("GET", "/sfa/v1/states")
    def states(call: HumbeeCall) -> Any:
        return {"states": [{"state_id": int(s.state_id), "state_name": s.name} for s in fake.states.values()]}

    @fake.route("GET", "/sfa/v1/districts")
    def districts(call: HumbeeCall) -> Any:
        state = fake.states[call.params["state_id"]]
        return {
            "districts": [
                {
                    "district_id": int(d.district_id),
                    "district_name": d.name,
                    "state_id": int(state.state_id),
                    "state_name": state.name,
                }
                for d in fake.districts.values()
                if d.state_id == state.state_id
            ]
        }

    @fake.route("GET", "/sfa/v1/locations")
    def locations(call: HumbeeCall) -> Any:
        return {
            "district_id": call.params["district_id"],
            "location_list": [{"location_id": LOCATION_ID, "location_name": "MG Road"}],
            "pincode_list": [{"pincode_id": PINCODE, "pincode_name": PINCODE}],
            "as_of": AS_OF,
        }

    @fake.route("GET", "/sfa/v1/manufacturer-roles")
    def manufacturer_roles(call: HumbeeCall) -> Any:
        return [
            {
                "manufacturer_id": MANUFACTURER_ID,
                "name": "Acme Cement",
                "vcp_roles": [
                    {
                        "role_id": FIRM_ROLE_ID,
                        "role_name": "Retailer",
                        "is_gst_required": True,
                        "is_pan_required": False,
                        "is_fssai_required": False,
                    }
                ],
                "influencer_roles": [],
            }
        ]
