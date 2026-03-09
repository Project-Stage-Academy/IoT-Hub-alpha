"""
Mock time/clock control for testing time-dependent behaviors.
Enables testing of cooldown periods, timeouts, and time-based rules.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

logger = logging.getLogger("telemetry.mock_time")


class MockClock:
    """
    Controllable clock for testing time-dependent code.

    Allows advancing time without waiting, freeze time at specific points,
    and verify time-based behaviors (cooldowns, timeouts, etc.).

    Thread Safety:
    - All time access protected by _lock
    - Safe for concurrent test execution

    Usage:
        clock = MockClock()
        clock.set_time("2026-03-01 12:00:00")

        # Advance time
        clock.advance(3600)  # Add 1 hour
        assert datetime.now() == "2026-03-01 13:00:00"

        # Reset
        clock.reset()
    """

    def __init__(self):
        self._current = datetime(2026, 3, 1, 12, 0, 0)
        self._lock = Lock()
        logger.info(f"MockClock initialized: {self._current}")

    def current_time(self) -> datetime:
        """Get current mock time."""
        with self._lock:
            return self._current

    def set_time(self, dt: datetime) -> None:
        """Set clock to specific time."""
        with self._lock:
            if isinstance(dt, str):
                self._current = datetime.fromisoformat(dt)
            else:
                self._current = dt
            logger.debug(f"Clock set to: {self._current}")

    def advance(self, seconds: float) -> None:
        """Advance clock by specified seconds."""
        with self._lock:
            self._current += timedelta(seconds=seconds)
            logger.debug(f"Clock advanced by {seconds}s, now: {self._current}")

    def advance_minutes(self, minutes: float) -> None:
        """Advance clock by specified minutes."""
        self.advance(minutes * 60)

    def advance_hours(self, hours: float) -> None:
        """Advance clock by specified hours."""
        self.advance(hours * 3600)

    def advance_days(self, days: float) -> None:
        """Advance clock by specified days."""
        self.advance(days * 86400)

    def reset(self) -> None:
        """Reset clock to default time (2026-03-01 12:00:00)."""
        with self._lock:
            self._current = datetime(2026, 3, 1, 12, 0, 0)
            logger.info(f"Clock reset to: {self._current}")

    def is_past(self, check_time: datetime) -> bool:
        """Check if current time is past specified time."""
        with self._lock:
            return self._current >= check_time

    def is_future(self, check_time: datetime) -> bool:
        """Check if current time is before specified time."""
        with self._lock:
            return self._current < check_time

    def time_until(self, target_time: datetime) -> float:
        """Get seconds until target time (negative if past)."""
        with self._lock:
            delta = target_time - self._current
            return delta.total_seconds()


@contextmanager
def TimeFreeze(initial_time: Optional[str] = None):
    """
    Context manager for freezing time during test.

    Provides MockClock instance that can be advanced within context.
    Clock is reset after context exits.

    Args:
        initial_time: ISO format datetime string (default: 2026-03-01 12:00:00)

    Usage:
        with TimeFreeze("2026-03-01 12:00:00") as clock:
            assert clock.current_time().hour == 12
            clock.advance_hours(1)
            assert clock.current_time().hour == 13
    """
    clock = MockClock()
    if initial_time:
        clock.set_time(initial_time)

    try:
        yield clock
    finally:
        clock.reset()


# Global shared mock clock (for testing that uses global time)
_shared_clock = MockClock()


def get_shared_clock() -> MockClock:
    """Get shared global clock (for tests that patch datetime.now())."""
    return _shared_clock


def reset_shared_clock() -> None:
    """Reset shared clock (call in test teardown)."""
    _shared_clock.reset()
