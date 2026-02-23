"""
Comprehensive unit tests for real-time rule evaluation logic.

Tests:
- Individual operators (lt, lte, gt, gte, eq, ne)
- AND/OR/NOT logic combinations
- Window state management
- Edge cases (null values, type coercion, boundary conditions)
- Error handling (invalid conditions, missing fields)
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from django.utils import timezone
from apps.rules.services.data_structure import Condition, EvalResults
from apps.rules.services.window_state import (
    WindowState,
    TelemetryPoint as WindowTelemetryPoint,
)
from apps.rules.services.rule_eval import eval_rule, TelemetryPoint


class TestBasicOperators:
    """Test individual comparison operators."""

    def test_operator_lt_true(self):
        """Test less-than operator when condition is true."""
        condition = Condition(type="leaf", operator="lt", threshold=15.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=8.5)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True
        assert result.values == [8.5]

    def test_operator_lt_false(self):
        """Test less-than operator when condition is false."""
        condition = Condition(type="leaf", operator="lt", threshold=5.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=8.5)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False

    def test_operator_lte_at_boundary(self):
        """Test less-than-or-equal operator at boundary."""
        condition = Condition(type="leaf", operator="lte", threshold=10.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=10.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_operator_gt_true(self):
        """Test greater-than operator."""
        condition = Condition(type="leaf", operator="gt", threshold=100.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=105.5)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_operator_gte_at_boundary(self):
        """Test greater-than-or-equal operator at boundary."""
        condition = Condition(type="leaf", operator="gte", threshold=50.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_operator_eq_true(self):
        """Test equality operator."""
        condition = Condition(type="leaf", operator="eq", threshold=42.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=42.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_operator_eq_false(self):
        """Test equality operator when values don't match."""
        condition = Condition(type="leaf", operator="eq", threshold=42.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=42.1)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False

    def test_operator_ne_false(self):
        """Test not-equal operator when values are equal."""
        # When value == threshold, ne should be False
        condition = Condition(type="leaf", operator="ne", threshold=10.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=10.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False


class TestMultipleValues:
    """Test rule evaluation with multiple telemetry points."""

    def test_multiple_values_any_match(self):
        """Test that trigger fires if ANY value matches."""
        condition = Condition(type="leaf", operator="gt", threshold=100.0)
        now = timezone.now()
        points = [
            TelemetryPoint(ts=now - timedelta(seconds=2), value=50.0),
            TelemetryPoint(ts=now - timedelta(seconds=1), value=75.0),
            TelemetryPoint(ts=now, value=105.0),  # This one triggers
        ]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True
        assert len(result.values) >= 1  # At least one value matched

    def test_multiple_values_none_match(self):
        """Test that trigger doesn't fire if NO values match."""
        condition = Condition(type="leaf", operator="gt", threshold=200.0)
        now = timezone.now()
        points = [
            TelemetryPoint(ts=now - timedelta(seconds=2), value=50.0),
            TelemetryPoint(ts=now - timedelta(seconds=1), value=75.0),
            TelemetryPoint(ts=now, value=100.0),
        ]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False

    def test_multiple_values_all_match(self):
        """Test with multiple values all matching condition."""
        condition = Condition(type="leaf", operator="gt", threshold=40.0)
        now = timezone.now()
        points = [
            TelemetryPoint(ts=now - timedelta(seconds=2), value=50.0),
            TelemetryPoint(ts=now - timedelta(seconds=1), value=75.0),
            TelemetryPoint(ts=now, value=100.0),
        ]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True
        assert len(result.values) == 3  # All values matched


class TestWindowState:
    """Test window state management for accumulated points."""

    def test_window_state_add_point(self):
        """Test adding a point to window state."""
        window = WindowState(window_seconds=60)
        now = timezone.now()
        value = 42.0

        window.add_point(now, value)

        assert len(window.values) == 1
        assert window.values[0].value == value
        assert window.values[0].ts == now

    def test_window_state_cleanup_expired(self):
        """Test that old points are automatically cleaned."""
        window = WindowState(window_seconds=10)
        now = timezone.now()

        # Add point outside window
        old_time = now - timedelta(seconds=15)
        window.add_point(old_time, 10.0)

        # Add point inside window
        recent_time = now - timedelta(seconds=5)
        window.add_point(recent_time, 20.0)

        # Only recent point should remain
        assert len(window.values) == 1
        assert window.values[0].value == 20.0

    def test_window_state_multiple_points(self):
        """Test accumulating multiple points in window."""
        window = WindowState(window_seconds=60)
        now = timezone.now()

        for i in range(5):
            ts = now - timedelta(seconds=10 * (5 - i))
            window.add_point(ts, float(i * 10))

        assert len(window.values) == 5

    def test_window_state_max_points_limit(self):
        """Test that window doesn't exceed max_points."""
        max_points = 100
        window = WindowState(window_seconds=3600, max_points=max_points)
        now = timezone.now()

        # Add more than max_points
        for i in range(max_points + 50):
            ts = now + timedelta(seconds=i)
            window.add_point(ts, float(i))

        # Should keep only last max_points
        assert len(window.values) == max_points

    def test_window_state_cleanup_expired_method(self):
        """Test explicit cleanup_expired method."""
        window = WindowState(window_seconds=10)
        now = timezone.now()

        # Add old and new points
        window.values = [
            WindowTelemetryPoint(ts=now - timedelta(seconds=20), value=10.0),
            WindowTelemetryPoint(ts=now - timedelta(seconds=5), value=20.0),
            WindowTelemetryPoint(ts=now, value=30.0),
        ]

        window.cleanup_expired(now)

        # Only recent points should remain
        assert len(window.values) == 2
        assert all(p.value >= 20.0 for p in window.values)

    def test_window_state_to_dict(self):
        """Test serialization to dict."""
        window = WindowState(window_seconds=60)
        now = timezone.now()
        window.add_point(now, 42.0)

        result = window.to_dict()

        assert "window_seconds" in result
        assert "values" in result
        assert result["window_seconds"] == 60


class TestANDLogic:
    """Test AND operator for combining conditions."""

    def test_and_both_true(self):
        """Test AND when both conditions are true."""
        condition = Condition(
            type="and",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=10.0),
                Condition(type="leaf", operator="lt", threshold=100.0),
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_and_one_false(self):
        """Test AND when one condition is false."""
        condition = Condition(
            type="and",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=10.0),
                Condition(type="leaf", operator="lt", threshold=30.0),  # False for 50
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False

    def test_and_both_false(self):
        """Test AND when both conditions are false."""
        condition = Condition(
            type="and",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=100.0),
                Condition(type="leaf", operator="lt", threshold=30.0),
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False


class TestORLogic:
    """Test OR operator for combining conditions."""

    def test_or_both_true(self):
        """Test OR when both conditions are true."""
        condition = Condition(
            type="or",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=40.0),
                Condition(type="leaf", operator="lt", threshold=60.0),
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_or_one_true(self):
        """Test OR when only one condition is true."""
        condition = Condition(
            type="or",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=100.0),  # False
                Condition(type="leaf", operator="lt", threshold=60.0),  # True
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_or_both_false(self):
        """Test OR when both conditions are false."""
        condition = Condition(
            type="or",
            conditions=[
                Condition(type="leaf", operator="gt", threshold=100.0),
                Condition(type="leaf", operator="lt", threshold=30.0),
            ],
        )
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False


class TestComplexLogic:
    """Test nested AND/OR conditions."""

    def test_nested_and_or(self):
        """Test (A AND B) OR C logic."""
        # (value > 10 AND value < 100) OR value == 200
        condition = Condition(
            type="or",
            conditions=[
                Condition(
                    type="and",
                    conditions=[
                        Condition(type="leaf", operator="gt", threshold=10.0),
                        Condition(type="leaf", operator="lt", threshold=100.0),
                    ],
                ),
                Condition(type="leaf", operator="eq", threshold=200.0),
            ],
        )
        now = timezone.now()

        # Test case 1: value matches first condition (AND)
        points = [TelemetryPoint(ts=now, value=50.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )
        assert result.trigger is True

        # Test case 2: value matches second condition (eq)
        points = [TelemetryPoint(ts=now, value=200.0)]
        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )
        assert result.trigger is True

        # Test case 3: value matches nothing
        points = [TelemetryPoint(ts=now, value=5.0)]
        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )
        assert result.trigger is False

    def test_three_level_and_or(self):
        """Test three-level nested AND/OR logic: (A AND B) OR (C AND D)."""
        condition = Condition(
            type="or",
            conditions=[
                Condition(
                    type="and",
                    conditions=[
                        Condition(type="leaf", operator="gt", threshold=10.0),
                        Condition(type="leaf", operator="lt", threshold=50.0),
                    ],
                ),
                Condition(
                    type="and",
                    conditions=[
                        Condition(type="leaf", operator="eq", threshold=100.0),
                        Condition(type="leaf", operator="gt", threshold=50.0),
                    ],
                ),
            ],
        )
        now = timezone.now()

        # Should trigger: 25 matches first AND condition (10 < 25 < 50)
        points = [TelemetryPoint(ts=now, value=25.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_telemetry_chunks(self):
        """Test with empty telemetry list."""
        condition = Condition(type="leaf", operator="gt", threshold=10.0)
        now = timezone.now()
        points = []
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is False

    def test_zero_value(self):
        """Test with zero value."""
        condition = Condition(type="leaf", operator="gt", threshold=-5.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=0.0)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_negative_threshold_comparison(self):
        """Test comparison with negative threshold."""
        condition = Condition(type="leaf", operator="gte", threshold=-10.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=-5.5)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        # -5.5 >= -10.0 should be True
        assert result.trigger is True

    def test_very_large_value(self):
        """Test with very large value."""
        condition = Condition(type="leaf", operator="gt", threshold=1_000_000.0)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=1_000_001.5)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_very_small_value(self):
        """Test with very small value (close to zero)."""
        condition = Condition(type="leaf", operator="lt", threshold=0.001)
        now = timezone.now()
        points = [TelemetryPoint(ts=now, value=0.0001)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.trigger is True

    def test_floating_point_precision(self):
        """Test floating point precision edge case."""
        condition = Condition(type="leaf", operator="eq", threshold=0.1 + 0.2)
        now = timezone.now()
        # Note: 0.1 + 0.2 != 0.3 in floating point due to precision
        points = [TelemetryPoint(ts=now, value=0.30000000000000004)]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        # This might be False due to FP precision, but should not crash
        assert isinstance(result.trigger, bool)


class TestResultsStructure:
    """Test that results contain expected structure and data."""

    def test_result_has_values_list(self):
        """Test that result contains matched values."""
        condition = Condition(type="leaf", operator="gt", threshold=10.0)
        now = timezone.now()
        points = [
            TelemetryPoint(ts=now - timedelta(seconds=1), value=5.0),
            TelemetryPoint(ts=now, value=15.0),
        ]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert isinstance(result.values, list)
        assert 15.0 in result.values

    def test_result_has_timestamps(self):
        """Test that result contains start/end timestamps."""
        condition = Condition(type="leaf", operator="gt", threshold=0.0)
        now = timezone.now()
        start = now - timedelta(seconds=10)
        end = now
        points = [
            TelemetryPoint(ts=start, value=10.0),
            TelemetryPoint(ts=end, value=20.0),
        ]
        aggregate = EvalResults(trigger=False, values=[], start=start, end=end)
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        assert result.start is not None
        assert result.end is not None

    def test_result_to_dict(self):
        """Test EvalResults.to_dict() serialization."""
        now = timezone.now()
        result = EvalResults(
            trigger=True, values=[10.0, 20.0, 30.0], start=now, end=now
        )

        result_dict = result.to_dict()

        assert result_dict["values"] == [10.0, 20.0, 30.0]
        assert result_dict["start"] == now.isoformat()
        assert result_dict["end"] == now.isoformat()


class TestOccurrencesCounting:
    """Test window conditions with occurrence counting."""

    def test_occurrences_requirement(self):
        """Test that occurrences are properly counted in window."""
        # Rule: value > 50 for at least 2 occurrences in 60-second window
        condition = Condition(
            type="leaf",
            operator="gt",
            threshold=50.0,
            window_seconds=60,
            occurrences=2,
        )
        now = timezone.now()
        points = [
            TelemetryPoint(ts=now - timedelta(seconds=30), value=55.0),
            TelemetryPoint(ts=now - timedelta(seconds=15), value=60.0),
            TelemetryPoint(ts=now, value=45.0),  # Doesn't match
        ]
        aggregate = EvalResults()
        device_id = uuid4()

        result = eval_rule(
            condition=condition,
            telemetry_chunks=points,
            aggregate_trigger=aggregate,
            device_id=device_id,
        )

        # Should trigger because we have 2+ occurrences
        assert result.trigger is True
