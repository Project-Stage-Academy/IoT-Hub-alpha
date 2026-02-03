from __future__ import annotations
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from apps.rules.services.rule_eval import TelemetryPoint, eval_rule
from apps.rules.services.data_structure import Condition, EvalResults


def tp(ts: datetime, value: float) -> TelemetryPoint:
    return TelemetryPoint(ts=ts, value=value)


def mk_leaf(operator: str, threshold: float) -> Condition:
    return Condition.model_validate(
        {"type": "leaf", "operator": operator, "threshold": threshold}
    )


def test_evalresults_to_dict_serializes_iso_datetimes():
    """
    Test correct serialization for DB write
    """
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    res = EvalResults(
        trigger=True, values=[1.0], start=t0, end=t0 + timedelta(seconds=5)
    )

    d = res.to_dict()

    assert d["values"] == [1.0]
    assert d["start"] == t0.isoformat()
    assert d["end"] == (t0 + timedelta(seconds=5)).isoformat()


@pytest.mark.parametrize(
    "op,threshold,values,expected_trigger,expected_values",
    [
        ("gt", 10.0, [9.0, 10.0, 11.0], True, [11.0]),
        ("gte", 10.0, [9.0, 10.0, 11.0], True, [10.0, 11.0]),
        ("lt", 10.0, [9.0, 10.0, 11.0], True, [9.0]),
        ("lte", 10.0, [9.0, 10.0, 11.0], True, [9.0, 10.0]),
        ("eq", 10.0, [9.0, 10.0, 11.0], True, [10.0]),
        ("ne", 10.0, [10.0], False, []),
    ],
)
def test_leaf_comparators(op, threshold, values, expected_trigger, expected_values):
    """
    Tests simple leaf operator condition
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0 + timedelta(seconds=i), v) for i, v in enumerate(values)]

    cond = mk_leaf(op, threshold)
    res = eval_rule(cond, points, EvalResults(), device_id)

    assert res.trigger is expected_trigger
    assert res.values == expected_values

    if expected_trigger:
        matching_idx = [i for i, v in enumerate(values) if v in expected_values]
        assert res.start == t0 + timedelta(seconds=min(matching_idx))
        assert res.end == t0 + timedelta(seconds=max(matching_idx))
    else:
        assert res.start is None
        assert res.end is None


def test_and_condition_requires_all_children():
    """
    AND passes when both children pass
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 15.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {"type": "leaf", "operator": "lt", "threshold": 20.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [15.0]


def test_and_condition_fails_if_any_child_fails_():
    """
    AND fails when both childen fails
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 25.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "lt", "threshold": 10.0},
                {"type": "leaf", "operator": "lt", "threshold": 20.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
    assert res.values == []


def test_and_condition_fails_if_right_child_fails_():
    """
    AND fails when left child fails
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 25.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "lt", "threshold": 10.0},
                {"type": "leaf", "operator": "gt", "threshold": 20.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
    assert res.values == []


def test_and_condition_fails_if_left_child_fails_():
    """
    AND fails when right child fails
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 15.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {"type": "leaf", "operator": "gt", "threshold": 20.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
    assert res.values == []


def test_or_condition_triggers_if_right_child_triggers():
    """
    OR triggers if right child triggers
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 15.0)]

    cond = Condition.model_validate(
        {
            "type": "or",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 100.0},
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [15.0]


def test_or_condition_triggers_if_left_child_triggers():
    """
    OR triggers if left child triggers
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 15.0)]

    cond = Condition.model_validate(
        {
            "type": "or",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {"type": "leaf", "operator": "gt", "threshold": 100.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [15.0]


def test_or_condition_triggers_if_both_child_triggers():
    """
    OR triggers if both children trigger
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 15.0)]

    cond = Condition.model_validate(
        {
            "type": "or",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {"type": "leaf", "operator": "gt", "threshold": 12.0},
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [15.0]


def test_window_eval_in_memory_triggers_when_n_points_in_window(monkeypatch):
    """
    Triggered points when window exceeds Celery's cooldown
    This forces celery to query telemetry instead of relying on batch data.
    """

    monkeypatch.setattr(
        "apps.rules.services.rule_eval.CELERY_PROCESS_TIMER",
        9999,
    )

    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)

    # 3 points within 10 seconds
    points = [
        tp(t0 + timedelta(seconds=1), 1.0),
        tp(t0 + timedelta(seconds=2), 2.0),
        tp(t0 + timedelta(seconds=9), 3.0),
    ]

    cond = Condition.model_validate(
        {
            "type": "leaf",
            "window_seconds": 10,
            "occurrences": 3,
            "operator": "gt",
            "threshold": 0.0,
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [1.0, 2.0, 3.0]
    assert res.start == t0 + timedelta(seconds=1)
    assert res.end == t0 + timedelta(seconds=9)


def test_window_eval_in_memory_fails_when_n_points_not_in_window(monkeypatch):
    """
    Does not trigger points when window exceeds Celery's cooldown and points are too far apart
    This forces celery to query telemetry instead of relying on batch data.
    """

    monkeypatch.setattr(
        "apps.rules.services.rule_eval.CELERY_PROCESS_TIMER",
        9999,
    )

    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)

    points = [
        tp(t0 + timedelta(seconds=1), 1.0),
        tp(t0 + timedelta(seconds=15), 15.0),
        tp(t0 + timedelta(seconds=25), 20.0),
    ]

    cond = Condition.model_validate(
        {
            "type": "leaf",
            "window_seconds": 10,
            "occurrences": 3,
            "operator": "gt",
            "threshold": 0.0,
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False


def test_window_eval_in_memory_does_not_trigger_if_count_not_met(monkeypatch):
    """
    Does not trigger points when window exceeds Celery's cooldown and points are insufficient
    This forces celery to query telemetry instead of relying on batch data.
    """
    monkeypatch.setattr("apps.rules.services.rule_eval.CELERY_PROCESS_TIMER", 9999)

    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)

    points = [
        tp(t0 + timedelta(seconds=1), 1.0),
    ]

    cond = Condition.model_validate(
        {
            "type": "leaf",
            "window_seconds": 10,
            "occurrences": 2,
            "operator": "gt",
            "threshold": 0.0,
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
    assert res.values == []


def test_window_eval_in_memory_dosent_trigger_within_latest_celery_cooldown(
    monkeypatch,
):
    """
    Does not trigger points when window is within Celery's cooldown and points are insufficient
    This uses telemetry from current batch
    """

    device_id = uuid4()
    t0 = datetime.now()

    points = [
        tp(t0 + timedelta(seconds=1), 1.0),
    ]

    cond = Condition.model_validate(
        {
            "type": "leaf",
            "window_seconds": 10,
            "occurrences": 2,
            "operator": "gt",
            "threshold": 0.0,
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
    assert res.values == []


def test_window_eval_in_memory_triggers_within_latest_celery_cooldown(monkeypatch):
    """
    Does not trigger points when window is within Celery's cooldown and points are too far apart
    This uses telemetry from current batch
    """

    device_id = uuid4()
    t0 = datetime.now()

    points = [
        tp(t0 + timedelta(seconds=1), 1.0),
        tp(t0 + timedelta(seconds=10), 2.0),
        tp(t0 + timedelta(seconds=21), 3.0),
    ]

    cond = Condition.model_validate(
        {
            "type": "leaf",
            "window_seconds": 10,
            "occurrences": 3,
            "operator": "gt",
            "threshold": 0.0,
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False


def test_nested_or_logic_pass():
    """
    OR triggers if both children trigger
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 18.0)]

    cond = Condition.model_validate(
        {
            "type": "or",
            "conditions": [
                {"type": "leaf", "operator": "lt", "threshold": 10.0},
                {
                    "type": "or",
                    "conditions": [
                        {"type": "leaf", "operator": "lt", "threshold": 15.0},
                        {"type": "leaf", "operator": "lt", "threshold": 20.0},
                    ],
                },
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [18.0]


def test_nested_or_logic_fail():
    """
    OR triggers if both children trigger
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 8.0)]

    cond = Condition.model_validate(
        {
            "type": "or",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {
                    "type": "or",
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 15.0},
                        {"type": "leaf", "operator": "gt", "threshold": 20.0},
                    ],
                },
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False


def test_nested_and_logic_pass():
    """
    OR triggers if both children trigger
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 18.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {
                    "type": "and",
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 15.0},
                        {"type": "leaf", "operator": "lt", "threshold": 20.0},
                    ],
                },
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is True
    assert res.values == [18.0]


def test_nested_and_logic_fail():
    """
    OR triggers if both children trigger
    """
    device_id = uuid4()
    t0 = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
    points = [tp(t0, 8.0)]

    cond = Condition.model_validate(
        {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 10.0},
                {
                    "type": "and",
                    "conditions": [
                        {"type": "leaf", "operator": "lt", "threshold": 15.0},
                        {"type": "leaf", "operator": "lt", "threshold": 20.0},
                    ],
                },
            ],
        }
    )

    res = eval_rule(cond, points, EvalResults(), device_id)
    assert res.trigger is False
