"""
Window state management for real-time rule evaluation.

Maintains sliding window of telemetry points for windowed rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List
from operator import gt, ge, lt, le, eq, ne


@dataclass(frozen=True)
class TelemetryPoint:
    """
    Immutable telemetry reading with timestamp and value.

    Frozen dataclass ensures point data cannot be modified after creation,
    making it safe to store in collections and share between threads.

    Attributes:
        ts: Timestamp when telemetry point was recorded (datetime)
        value: Numeric telemetry value (float, e.g., temperature, humidity, RPM)
    """

    ts: datetime
    value: float


@dataclass
class WindowState:
    """
    Maintains sliding window of telemetry points for real-time rule evaluation.

    Implements a fixed-size sliding window that automatically discards expired points
    and prevents unbounded memory growth. Used by rules that need to evaluate conditions
    over accumulated historical data (e.g., "average > 80 over last 5 minutes").

    Window Management:
    - Points older than window_seconds are removed periodically (not on every add)
    - Memory is capped at max_points to prevent runaway memory usage
    - Cleanup runs every cleanup_interval points to reduce O(n) filter overhead
    - Cleanup can also be triggered explicitly via cleanup_expired()

    Performance Optimization:
    - Cleanup every N points instead of every add_point() call
    - Reduces O(n) filtering from O(points/sec) to O(points/sec / cleanup_interval)
    - Example: 1000 msg/sec with cleanup_interval=100 reduces 1000x filtering to 10x

    Example Usage:
        window = WindowState(window_seconds=300)  # 5 minute window
        window.add_point(datetime.now(), 25.0)
        matching = window.get_matching_points("gt", 20.0)
        count = len(matching)

    Attributes:
        window_seconds: Time window size in seconds (default: 60)
        max_points: Maximum points to retain (default: 10,000)
        cleanup_interval: Run cleanup every N point additions (default: 100)
        values: List of TelemetryPoint objects currently in window
        points_since_cleanup: Counter for cleanup interval tracking (internal)
    """

    window_seconds: int = 60
    max_points: int = 10_000
    cleanup_interval: int = 100
    values: List[TelemetryPoint] = field(default_factory=list)
    points_since_cleanup: int = field(default=0, init=False, repr=False)

    def add_point(self, ts: datetime, value: float) -> None:
        """
        Add telemetry point to window with periodic cleanup of expired points.

        Performs two operations:
        1. Add new TelemetryPoint to window
        2. If cleanup_interval points have been added, remove expired points

        Periodic cleanup reduces O(n) filtering overhead:
        - Cleanup every N points instead of every add_point() call
        - High-frequency telemetry (1000 msg/sec) benefits significantly
        - Expired points are still kept between cleanups (acceptable tradeoff)

        Memory is also capped at max_points to prevent unbounded growth.

        Args:
            ts: Timestamp of telemetry reading (datetime)
            value: Numeric telemetry value (float)

        Side Effects:
        - Modifies self.values list (adds point)
        - Periodically removes old points and may truncate (every cleanup_interval calls)
        """
        # Always add the new point
        self.values.append(TelemetryPoint(ts=ts, value=value))
        self.points_since_cleanup += 1

        # Cleanup periodically (not on every add_point call)
        if self.points_since_cleanup >= self.cleanup_interval:
            cutoff = ts - timedelta(seconds=self.window_seconds)
            self.values = [p for p in self.values if p.ts > cutoff]
            self.points_since_cleanup = 0

        # Cap at max_points (keep most recent)
        if len(self.values) > self.max_points:
            self.values = self.values[-self.max_points :]

    def get_matching_points(
        self, operator: str, threshold: float
    ) -> List[TelemetryPoint]:
        """
        Filter window points by comparison operator and threshold.

        Applies comparison operator to each point's value and returns matching points.
        Used by rule evaluation to count occurrences or aggregate matching telemetry
        data.

        Example:
            window.add_point(ts1, 25.0)
            window.add_point(ts2, 15.0)
            window.add_point(ts3, 35.0)
            matching = window.get_matching_points("gt", 20.0)
            # Returns: [TelemetryPoint(ts1, 25.0), TelemetryPoint(ts3, 35.0)]

        Args:
            operator: Comparison operator string ("gt", "gte", "lt", "lte",
                     "eq", "ne")
            threshold: Numeric threshold to compare against

        Returns:
            List of TelemetryPoint objects where value OP threshold evaluates to True.
            Empty list if no points match or operator is invalid.

        Performance:
            O(n) where n = number of points in window (typically < 1000)
        """
        ops = {"gt": gt, "gte": ge, "lt": lt, "lte": le, "eq": eq, "ne": ne}
        cmp = ops.get(operator)

        if cmp is None:
            return []

        return [p for p in self.values if cmp(p.value, threshold)]

    def cleanup_expired(self, now: datetime) -> None:
        """
        Explicitly remove telemetry points older than window (manual cleanup).

        Called periodically by evaluator.clear_old_states() or when device stops
        sending telemetry. Unlike add_point() which does periodic cleanup, this
        always cleans up immediately and resets the cleanup counter.

        Useful for:
        - Reducing memory when device stops sending telemetry
        - Maintenance operations during low-traffic periods
        - Ensuring cleanup even if cleanup_interval not reached
        - Explicit control over cleanup timing

        Args:
            now: Current timestamp (reference point for age calculation)
                 Points with ts <= (now - window_seconds) will be removed

        Side Effects:
        - Modifies self.values list (removes expired points)
        - Resets points_since_cleanup counter
        """
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.values = [p for p in self.values if p.ts > cutoff]
        self.points_since_cleanup = 0

    def to_dict(self) -> dict:
        """
        Serialize window state to JSON-compatible dict (for persistence if needed).

        Converts window state to plain dict with ISO format timestamps, suitable for
        JSON serialization or Redis storage. Future enhancement could persist window
        states across process restarts via Redis or database.

        Returns:
            Dict with keys:
            - window_seconds: int (window configuration)
            - values: list of dicts with keys "ts" (ISO string) and "value" (float)

        Example:
            state = WindowState(window_seconds=300)
            state.add_point(datetime(2026, 2, 19, 12, 0, 0), 25.0)
            data = state.to_dict()
            # Returns: {
            #     'window_seconds': 300,
            #     'values': [{'ts': '2026-02-19T12:00:00', 'value': 25.0}]
            # }
        """
        return {
            "window_seconds": self.window_seconds,
            "values": [{"ts": p.ts.isoformat(), "value": p.value} for p in self.values],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WindowState":
        """
        Deserialize window state from JSON-compatible dict (inverse of to_dict).

        Reconstructs WindowState from serialized dict. Used to restore window states
        that were persisted to Redis, database, or other storage. Handles conversion
        of ISO timestamp strings back to datetime objects.

        Args:
            data: Dict with structure from to_dict():
                  - window_seconds: int (required)
                  - values: list of dicts with "ts" (ISO string) and "value" (float)

        Returns:
            WindowState instance with restored window_seconds and TelemetryPoint values

        Example:
            data = {
                'window_seconds': 300,
                'values': [{'ts': '2026-02-19T12:00:00', 'value': 25.0}]
            }
            state = WindowState.from_dict(data)
            # state.window_seconds == 300
            # len(state.values) == 1
        """
        state = cls(window_seconds=data["window_seconds"])
        state.values = [
            TelemetryPoint(
                ts=datetime.fromisoformat(v["ts"]),
                value=v["value"],
            )
            for v in data.get("values", [])
        ]
        return state
