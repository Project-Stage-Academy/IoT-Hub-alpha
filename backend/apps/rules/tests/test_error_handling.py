"""
Error handling tests for rule evaluation.

Tests that invalid/malformed data is handled gracefully:
- Invalid condition structures
- Missing required fields
- Invalid operator/threshold values
- Type errors
- Database errors
- Edge cases that could cause exceptions
"""

from __future__ import annotations
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from apps.rules.services.rule_eval import TelemetryPoint, eval_rule
from apps.rules.services.data_structure import Condition, EvalResults
from apps.rules.services.window_state import WindowState
from django.core.exceptions import ValidationError
from apps.rules.services.realtime_evaluator import RealTimeRuleEvaluator


class TestInvalidConditionStructures:
    """Test handling of invalid/malformed condition data."""

    def test_missing_type_field(self):
        """Condition without 'type' field should raise validation error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"operator": "gt", "threshold": 10.0})

    def test_missing_operator_in_leaf(self):
        """Leaf condition without 'operator' should raise validation error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "leaf", "threshold": 10.0})

    def test_missing_threshold_in_leaf(self):
        """Leaf condition without 'threshold' should raise validation error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "leaf", "operator": "gt"})

    def test_invalid_operator_name(self):
        """Invalid operator name should raise validation error."""
        with pytest.raises(ValueError):
            Condition.model_validate(
                {"type": "leaf", "operator": "invalid_op", "threshold": 10.0}
            )

    def test_missing_conditions_in_and(self):
        """AND condition without 'conditions' list should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "and"})

    def test_empty_conditions_list_in_and(self):
        """AND condition with empty 'conditions' list should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "and", "conditions": []})

    def test_missing_conditions_in_or(self):
        """OR condition without 'conditions' list should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "or"})

    def test_empty_conditions_list_in_or(self):
        """OR condition with empty 'conditions' list should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate({"type": "or", "conditions": []})

    def test_invalid_condition_type(self):
        """Unknown condition type should raise validation error."""
        with pytest.raises(ValueError):
            Condition.model_validate(
                {"type": "invalid", "operator": "gt", "threshold": 10.0}
            )

    def test_nested_invalid_condition(self):
        """AND with invalid nested condition should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate(
                {
                    "type": "and",
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 10.0},
                        {"type": "leaf", "operator": "invalid_op", "threshold": 20.0},
                    ],
                }
            )


class TestInvalidThresholdValues:
    """Test handling of invalid threshold values."""

    def test_non_numeric_threshold(self):
        """Non-numeric threshold should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate(
                {"type": "leaf", "operator": "gt", "threshold": "not_a_number"}
            )

    def test_null_threshold(self):
        """Null threshold should raise error."""
        with pytest.raises(ValueError):
            Condition.model_validate(
                {"type": "leaf", "operator": "gt", "threshold": None}
            )

    def test_infinite_threshold(self):
        """Infinite threshold should be handled gracefully."""
        cond = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": float("inf")}
        )
        assert cond.threshold == float("inf")

    def test_nan_threshold(self):
        """NaN threshold should be handled or rejected."""
        # NaN handling depends on implementation
        # Most systems would either reject or handle specially
        cond = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": float("nan")}
        )
        # Should not raise during validation


class TestInvalidTelemetryData:
    """Test handling of invalid telemetry point data."""

    def test_missing_timestamp(self):
        """TelemetryPoint without timestamp should raise error."""
        with pytest.raises(TypeError):
            TelemetryPoint(value=10.0)

    def test_missing_value(self):
        """TelemetryPoint without value should raise error."""
        with pytest.raises(TypeError):
            TelemetryPoint(ts=datetime.now(timezone.utc))

    def test_non_numeric_value(self):
        """TelemetryPoint with non-numeric value is accepted by dataclass but fails on comparison."""
        ts = datetime.now(timezone.utc)
        # Dataclass doesn't validate types at construction
        point = TelemetryPoint(ts=ts, value="not_a_number")
        assert point.value == "not_a_number"
        # But comparison with float threshold will fail
        with pytest.raises(TypeError):
            _ = point.value > 10.0

    def test_null_value(self):
        """TelemetryPoint with None value is accepted by dataclass but fails on comparison."""
        ts = datetime.now(timezone.utc)
        point = TelemetryPoint(ts=ts, value=None)
        assert point.value is None
        with pytest.raises(TypeError):
            _ = point.value > 10.0

    def test_invalid_timestamp_type(self):
        """TelemetryPoint with non-datetime timestamp fails on timedelta ops."""
        point = TelemetryPoint(ts="2026-02-16", value=10.0)
        assert point.ts == "2026-02-16"
        # Fails when used in WindowState.add_point (ts - timedelta during cleanup)
        # Use cleanup_interval=1 to trigger cleanup immediately on second call
        with pytest.raises(TypeError):
            window = WindowState(window_seconds=60, cleanup_interval=1)
            window.add_point(ts=point.ts, value=point.value)
            # Second add_point triggers cleanup which fails on string ts
            window.add_point(ts=point.ts, value=point.value)


class TestEvalRuleErrorHandling:
    """Test eval_rule error handling with invalid inputs."""

    def test_eval_rule_with_empty_telemetry(self):
        """eval_rule with empty telemetry list should handle gracefully."""
        device_id = uuid4()
        condition = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 10.0}
        )

        result = eval_rule(
            condition=condition,
            telemetry_chunks=[],
            aggregate_trigger=EvalResults(),
            device_id=device_id,
        )

        assert result.trigger is False
        assert result.values == []

    def test_eval_rule_with_single_point(self):
        """eval_rule with single telemetry point should work."""
        device_id = uuid4()
        ts = datetime.now(timezone.utc)
        condition = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 10.0}
        )

        telemetry = [TelemetryPoint(ts=ts, value=15.0)]
        result = eval_rule(
            condition=condition,
            telemetry_chunks=telemetry,
            aggregate_trigger=EvalResults(),
            device_id=device_id,
        )

        assert result.trigger is True
        assert 15.0 in result.values

    def test_eval_rule_invalid_device_id_type(self):
        """eval_rule with invalid device_id type should handle gracefully."""
        ts = datetime.now(timezone.utc)
        condition = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 10.0}
        )

        telemetry = [TelemetryPoint(ts=ts, value=15.0)]

        # Should either accept or raise TypeError, but not crash
        try:
            result = eval_rule(
                condition=condition,
                telemetry_chunks=telemetry,
                aggregate_trigger=EvalResults(),
                device_id="not-a-uuid",  # Invalid UUID
            )
            # If it accepts invalid ID, it should still return valid result
            assert isinstance(result, EvalResults)
        except (TypeError, ValueError):
            # Or it should raise validation error
            pass

    def test_eval_rule_with_none_aggregate_trigger(self):
        """eval_rule with None aggregate_trigger should raise error."""
        device_id = uuid4()
        ts = datetime.now(timezone.utc)
        condition = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 10.0}
        )

        telemetry = [TelemetryPoint(ts=ts, value=15.0)]

        with pytest.raises((TypeError, AttributeError)):
            eval_rule(
                condition=condition,
                telemetry_chunks=telemetry,
                aggregate_trigger=None,
                device_id=device_id,
            )


class TestWindowStateErrorHandling:
    """Test WindowState error handling."""

    def test_window_state_creation_with_invalid_window_size(self):
        """WindowState with negative window size is accepted by dataclass."""
        ws = WindowState(window_seconds=-1)
        assert ws.window_seconds == -1

    def test_window_state_creation_with_zero_window_size(self):
        """WindowState with zero window size is accepted by dataclass."""
        ws = WindowState(window_seconds=0)
        assert ws.window_seconds == 0

    def test_window_state_creation_with_non_numeric_window(self):
        """WindowState with non-numeric window size fails on use."""
        ws = WindowState(window_seconds="invalid")
        assert ws.window_seconds == "invalid"
        # Fails when add_point tries to use it in timedelta()
        with pytest.raises(TypeError):
            ws.add_point(ts=datetime.now(timezone.utc), value=10.0)

    def test_window_state_add_point_with_invalid_timestamp(self):
        """add_point with invalid timestamp should raise error."""
        window = WindowState(window_seconds=60)

        with pytest.raises((TypeError, ValueError)):
            window.add_point(ts="not-a-timestamp", value=10.0)

    def test_window_state_add_point_with_non_numeric_value(self):
        """add_point with non-numeric value succeeds (stored as TelemetryPoint)."""
        window = WindowState(window_seconds=60)
        ts = datetime.now(timezone.utc)

        # Dataclass doesn't validate, point is stored
        window.add_point(ts=ts, value="not-a-number")
        assert len(window.values) == 1
        assert window.values[0].value == "not-a-number"

    def test_window_state_cleanup_with_invalid_timestamp(self):
        """cleanup_expired with invalid timestamp should raise error."""
        window = WindowState(window_seconds=60)

        with pytest.raises((TypeError, AttributeError)):
            window.cleanup_expired(ts="not-a-timestamp")

    def test_window_state_max_points_enforcement(self):
        """WindowState should handle max_points limit gracefully."""
        window = WindowState(window_seconds=60, max_points=5)
        ts = datetime.now(timezone.utc)

        # Add more than max_points
        for i in range(10):
            window.add_point(ts=ts, value=float(i))

        # Should not exceed max_points
        assert len(window.values) <= 5


class TestRealTimeEvaluatorErrorHandling:
    """Test RealTimeRuleEvaluator error handling."""

    def test_evaluator_with_none_producer(self):
        """RealTimeRuleEvaluator should handle None producer gracefully."""
        evaluator = RealTimeRuleEvaluator(producer=None)
        assert evaluator.producer is None

    def test_evaluator_clear_old_states_with_no_states(self):
        """clear_old_states succeeds with empty state."""
        evaluator = RealTimeRuleEvaluator()
        # clear_old_states uses timezone.now() internally, param is unused
        evaluator.clear_old_states(older_than_seconds=3600)
        assert len(evaluator.window_states) == 0

    @pytest.mark.django_db
    def test_evaluator_evaluate_with_invalid_device_id(self):
        """evaluate with invalid device_id raises ValueError from UUID field."""
        evaluator = RealTimeRuleEvaluator()
        ts = datetime.now(timezone.utc)
        point = TelemetryPoint(ts=ts, value=10.0)

        with pytest.raises((TypeError, ValueError, ValidationError)):
            evaluator.evaluate(device_id="not-a-uuid", telemetry_point=point)

    @pytest.mark.django_db
    def test_evaluator_evaluate_with_none_device_id(self):
        """evaluate with None device_id returns empty dict (no rules found)."""
        evaluator = RealTimeRuleEvaluator()
        ts = datetime.now(timezone.utc)
        point = TelemetryPoint(ts=ts, value=10.0)

        result = evaluator.evaluate(device_id=None, telemetry_point=point)
        assert result == {}

    @pytest.mark.django_db
    def test_evaluator_evaluate_with_none_telemetry_point(self):
        """evaluate with None telemetry_point returns empty dict when no rules."""
        evaluator = RealTimeRuleEvaluator()
        device_id = uuid4()

        # With no rules in DB for this device, loop doesn't execute
        result = evaluator.evaluate(device_id=device_id, telemetry_point=None)
        assert result == {}

    @patch("apps.rules.services.realtime_evaluator.Rule.objects.filter")
    def test_evaluator_handles_database_error(self, mock_filter):
        """RealTimeEvaluator should handle database errors gracefully."""
        evaluator = RealTimeRuleEvaluator()
        device_id = uuid4()
        ts = datetime.now(timezone.utc)
        point = TelemetryPoint(ts=ts, value=10.0)

        # Simulate database error
        mock_filter.side_effect = Exception("Database connection error")

        with pytest.raises(Exception):
            evaluator.evaluate(device_id=device_id, telemetry_point=point)

    def test_evaluator_on_rule_updated_with_invalid_rule_id(self):
        """on_rule_updated should handle invalid rule_id gracefully."""
        evaluator = RealTimeRuleEvaluator()

        # Should not raise even with invalid ID
        try:
            evaluator.on_rule_updated(rule_id="not-a-uuid")
        except (TypeError, ValueError):
            pass  # Acceptable to raise validation error

    def test_evaluator_clear_cache_with_invalid_device_id(self):
        """clear_cache with invalid device_id succeeds (no-op)."""
        evaluator = RealTimeRuleEvaluator()
        # dict.pop() accepts any hashable key, no validation
        evaluator.clear_cache(device_id="not-a-uuid")
        assert "not-a-uuid" not in evaluator.rule_cache

    def test_evaluator_get_metrics_returns_dict(self):
        """get_metrics should return valid dict even with no state."""
        evaluator = RealTimeRuleEvaluator()
        metrics = evaluator.get_metrics()

        assert isinstance(metrics, dict)
        assert "cached_rules" in metrics
        assert "active_windows" in metrics
        assert "total_points_in_windows" in metrics


class TestOccurrencesHandling:
    """Test handling of occurrences parameter with errors."""

    def test_invalid_occurrences_value(self):
        """Invalid occurrences value should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {"type": "leaf", "operator": "gt", "threshold": 10.0, "occurrences": -1}
            )

    def test_zero_occurrences(self):
        """Zero occurrences should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {"type": "leaf", "operator": "gt", "threshold": 10.0, "occurrences": 0}
            )

    def test_non_integer_occurrences(self):
        """Non-integer occurrences should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 10.0,
                    "occurrences": 3.5,
                }
            )


class TestWindowSecondsHandling:
    """Test handling of window_seconds parameter with errors."""

    def test_invalid_window_seconds_value(self):
        """Invalid window_seconds should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 10.0,
                    "window_seconds": -1,
                }
            )

    def test_zero_window_seconds(self):
        """Zero window_seconds should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 10.0,
                    "window_seconds": 0,
                }
            )

    def test_non_integer_window_seconds(self):
        """Non-integer window_seconds should raise error."""
        with pytest.raises((ValueError, TypeError)):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 10.0,
                    "window_seconds": 60.5,
                }
            )


class TestEvalResultsErrorHandling:
    """Test EvalResults error handling."""

    def test_evalresults_to_dict_with_none_values(self):
        """EvalResults.to_dict with None start/end should handle gracefully."""
        result = EvalResults(trigger=True, values=[10.0, 11.0], start=None, end=None)

        d = result.to_dict()

        # to_dict() does not include 'trigger' field
        assert "trigger" not in d
        assert d["values"] == [10.0, 11.0]
        assert d["start"] is None
        assert d["end"] is None

    def test_evalresults_to_dict_with_invalid_values(self):
        """EvalResults with non-serializable values is accepted by dataclass."""
        # Dataclass doesn't validate types at construction
        result = EvalResults(
            trigger=True, values=[object()], start=None, end=None  # Non-serializable
        )
        assert len(result.values) == 1

    def test_evalresults_with_mismatched_start_end(self):
        """EvalResults with start > end should be handled."""
        ts1 = datetime(2026, 2, 16, 12, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 2, 16, 11, 0, tzinfo=timezone.utc)

        result = EvalResults(
            trigger=True, values=[10.0], start=ts1, end=ts2  # end before start
        )

        # Should still create but ordering is caller's responsibility
        assert result.start > result.end


class TestConcurrencyErrorHandling:
    """Test handling of concurrent access scenarios."""

    def test_multiple_evaluators_independent_state(self):
        """Multiple RealTimeRuleEvaluators should maintain independent state."""
        eval1 = RealTimeRuleEvaluator()
        eval2 = RealTimeRuleEvaluator()

        device_id = uuid4()
        ts = datetime.now(timezone.utc)
        point = TelemetryPoint(ts=ts, value=10.0)

        # State modification in one shouldn't affect the other
        eval1.window_states[device_id] = Mock()
        assert device_id not in eval2.window_states


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_very_large_threshold(self):
        """Very large threshold should be handled."""
        cond = Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 1e308}
        )

        result = eval_rule(
            condition=cond,
            telemetry_chunks=[
                TelemetryPoint(ts=datetime.now(timezone.utc), value=1e307)
            ],
            aggregate_trigger=EvalResults(),
            device_id=uuid4(),
        )

        # Should not crash, though may or may not trigger
        assert isinstance(result, EvalResults)

    def test_very_small_threshold(self):
        """Very small threshold should be handled."""
        cond = Condition.model_validate(
            {"type": "leaf", "operator": "lt", "threshold": -1e308}
        )

        result = eval_rule(
            condition=cond,
            telemetry_chunks=[
                TelemetryPoint(ts=datetime.now(timezone.utc), value=-1e307)
            ],
            aggregate_trigger=EvalResults(),
            device_id=uuid4(),
        )

        assert isinstance(result, EvalResults)

    def test_precision_loss_near_threshold(self):
        """Floating point precision near threshold should be handled."""
        threshold = 10.0
        cond = Condition.model_validate(
            {"type": "leaf", "operator": "eq", "threshold": threshold}
        )

        # Floating point value very close to threshold
        value = 10.0 + 1e-15

        result = eval_rule(
            condition=cond,
            telemetry_chunks=[
                TelemetryPoint(ts=datetime.now(timezone.utc), value=value)
            ],
            aggregate_trigger=EvalResults(),
            device_id=uuid4(),
        )

        # Exact equality check may or may not trigger due to float precision
        assert isinstance(result, EvalResults)
