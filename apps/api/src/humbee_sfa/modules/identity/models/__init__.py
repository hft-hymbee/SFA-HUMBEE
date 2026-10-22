"""`identity` models. `Employee` lives in `org`; this module reads it through `org.service`,
never its own model.

- `otp_challenge.py`   `identity_otp_challenges` — phone + OTP login challenges.
- `device.py`          `identity_devices` — one row per installed client.
- `session.py`         `identity_sessions` — refresh-token rotation/revocation only.
- `auth_audit_event.py`  `identity_auth_audit_events` — append-only auth trail.
"""

from __future__ import annotations

from humbee_sfa.modules.identity.models.auth_audit_event import AuthAuditEvent
from humbee_sfa.modules.identity.models.device import Device
from humbee_sfa.modules.identity.models.otp_challenge import OtpChallenge
from humbee_sfa.modules.identity.models.session import Session

__all__ = ["AuthAuditEvent", "Device", "OtpChallenge", "Session"]
