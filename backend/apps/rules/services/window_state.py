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
    - Points older than window_seconds are automatically removed on add_point()
    - Memory is capped at max_points to prevent runaway memory usage
    - Cleanup can also be triggered explicitly via cleanup_expired()

    Example Usage:
        window = WindowState(window_seconds=300)  # 5 minute window
        window.add_point(datetime.now(), 25.0)
        matching = window.get_matching_points("gt", 20.0)
        count = len(matching)

    Attributes:
        window_seconds: Time window size in seconds (default: 60)
        max_points: Maximum points to retain (default: 10,000)
        values: List of TelemetryPoint objects currently in window
    """

    window_seconds: int = 60
    max_points: int = 10_000
    values: List[TelemetryPoint] = field(default_factory=list)

    def add_point(self, ts: datetime, value: float) -> None:
        """
        Add telemetry point to window with automatic cleanup of expired points.

        Performs three operations atomically:
        1. Remove all points older than (ts - window_seconds)
        2. Add new TelemetryPoint to window
        3. Truncate to max_points if exceeded (keeps most recent points)

        This ensures the window always contains only relevant recent data and
        prevents unbounded memory growth even with continuous high-rate telemetry.

        Args:
            ts: Timestamp of telemetry reading (datetime)
            value: Numeric telemetry value (float)

        Side Effects:
        - Modifies self.values list (adds point, removes old points, may truncate)
        """
        cutoff = ts - timedelta(seconds=self.window_seconds)
        self.values = [p for p in self.values if p.ts > cutoff]

        self.values.append(TelemetryPoint(ts=ts, value=value))

        if len(self.values) > self.max_points:
            self.values = self.values[-self.max_points :]

    def get_matching_points(
        self, operator: str, threshold: float
    ) -> List[TelemetryPoint]:
        """
        Filter window points by comparison operator and threshold.

        Applies comparison operator to each point's value and returns matching points.
        Used by rule evaluation to count occurrences or aggregate matching telemetry.

        Example:
            window.add_point(ts1, 25.0)
            window.add_point(ts2, 15.0)
            window.add_point(ts3, 35.0)
            matching = window.get_matching_points("gt", 20.0)
            # Returns: [TelemetryPoint(ts1, 25.0), TelemetryPoint(ts3, 35.0)]

        Args:
            operator: Comparison operator as string: "gt", "gte", "lt", "lte", "eq", "ne"
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

        Called periodically by evaluator.clear_old_states() to prevent window
        states from accumulating stale points. Automatically called by add_point()
        but this explicit cleanup is useful for:
        - Reducing memory when device stops sending telemetry
        - Maintenance operations during low-traffic periods
        - Ensuring periodic cleanup even if no new points arrive

        Args:
            now: Current timestamp (reference point for age calculation)
                 Points with ts <= (now - window_seconds) will be removed

        Side Effects:
        - Modifies self.values list (removes expired points)
        """
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.values = [p for p in self.values if p.ts > cutoff]

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
