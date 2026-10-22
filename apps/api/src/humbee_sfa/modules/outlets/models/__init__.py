"""`outlets` models — Humbee outlet projection and the firm-onboarding flow.

- `outlet.py`                  `Outlet` — tenant-scoped projection of Humbee outlet master data.
- `onboarding_candidate.py`    `OutletOnboardingCandidate` — `outlets_onboarding_candidates`, a
  field-captured firm held locally until a manager approves it, because ON-3 is irreversible.
- `owner_otp_challenge.py`     `OwnerOtpChallenge` — `outlets_owner_otp_challenges`, phone
  verification for a prospective firm owner ahead of ON-3 `onboard-firm`.

`OutletVerificationTimeline` (a projection over `approvals_decisions`) and `OutletInsight` (rendered
externally, never persisted, R-OUT-30) are not tables — there is no ORM model for either.
"""

from __future__ import annotations

from humbee_sfa.modules.outlets.models.onboarding_candidate import OutletOnboardingCandidate
from humbee_sfa.modules.outlets.models.outlet import Outlet
from humbee_sfa.modules.outlets.models.owner_otp_challenge import OwnerOtpChallenge

__all__ = [
    "Outlet",
    "OutletOnboardingCandidate",
    "OwnerOtpChallenge",
]
