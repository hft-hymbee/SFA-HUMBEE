"""Clock abstractions for deterministic, testable time access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime:
        """Return the current UTC timestamp."""


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


def utc_now() -> datetime:
    """Canonical UTC now helper for callers without DI."""

    return SystemClock().now_utc()
