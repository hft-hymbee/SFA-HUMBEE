"""`notifications` models — database-design.md §6. Read this file for the index; open the module
for column detail.

- `notification.py`  `Notification` — `notifications`, the in-app notification feed, deduplicated
  per recipient via `uq_notifications_dedupe`.
"""

from __future__ import annotations

from humbee_sfa.modules.notifications.models.notification import Notification

__all__ = [
    "Notification",
]
