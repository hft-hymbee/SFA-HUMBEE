"""`beats` models. Read this file for the index; open a specific module
for column detail.

- `beat.py`                    `Beat` — `beats`, the beat master (lifecycle + activation state).
- `beat_version.py`            `BeatVersion` — `beats_versions`, versioned territory/cadence snapshot.
- `beat_outlet.py`              `BeatOutlet` — `beats_outlets`, outlet-grained beat-version membership.
- `beat_edit_request.py`        `BeatEditRequest` — `beats_edit_requests`, pending edits to an
  approved beat.
- `beat_activation_event.py`    `BeatActivationEvent` — `beats_activation_events`, append-only
  deactivate/reactivate audit trail.
"""

from __future__ import annotations

from humbee_sfa.modules.beats.models.beat import Beat
from humbee_sfa.modules.beats.models.beat_activation_event import BeatActivationEvent
from humbee_sfa.modules.beats.models.beat_edit_request import BeatEditRequest
from humbee_sfa.modules.beats.models.beat_outlet import BeatOutlet
from humbee_sfa.modules.beats.models.beat_version import BeatVersion

__all__ = [
    "Beat",
    "BeatActivationEvent",
    "BeatEditRequest",
    "BeatOutlet",
    "BeatVersion",
]
