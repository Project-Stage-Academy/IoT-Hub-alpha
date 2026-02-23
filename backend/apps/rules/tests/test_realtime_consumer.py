"""
Tests for real-time rule consumer.
Uses mock Kafka to avoid needing real Kafka.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from apps.rules.services.mock_kafka import (
    MockProducer,
    MockConsumer,
    reset_mock_topics,
    get_mock_topic_messages,
)
from apps.rules.services.realtime_evaluator import RealTimeRuleEvaluator
from apps.rules.services.window_state import TelemetryPoint
from apps.rules.models import Rule
from apps.devices.models import Device, DeviceType


@pytest.fixture
def setup_mock_kafka():
    """Reset mock Kafka before each test"""
    reset_mock_topics()
    yield
    reset_mock_topics()


@pytest.fixture
def mock_producer_consumer():
    """Create mock producer/consumer pair"""
    producer = MockProducer()
    consumer = MockConsumer({"group.id": "test-group"})
    return producer, consumer


@pytest.mark.django_db
def test_mock_kafka_basic(mock_producer_consumer, setup_mock_kafka):
    """Test basic mock Kafka producer/consumer"""
    producer, consumer = mock_producer_consumer

    # Produce message
    producer.send("test-topic", {"value": 42.0})

    # Consume message
    consumer.subscribe(["test-topic"])
    msg = consumer.poll()

    assert msg is not None
    payload = json.loads(msg.value().decode("utf-8"))
    assert payload["value"] == 42.0


@pytest.mark.django_db
def test_evaluator_with_single_rule():
    """Test evaluator with single rule"""
    from apps.rules.services.data_structure import Condition

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="Temp > 20",
        condition={"type": "leaf", "operator": "gt", "threshold": 20.0},
        action_config=[],
        is_enabled=True,
    )

    evaluator = RealTimeRuleEvaluator()

    # Test below threshold
    point1 = TelemetryPoint(ts=datetime.now(timezone.utc), value=15.0)
    triggered = evaluator.evaluate(device.id, point1)
    assert len(triggered) == 0

    # Test above threshold
    point2 = TelemetryPoint(ts=datetime.now(timezone.utc), value=25.0)
    triggered = evaluator.evaluate(device.id, point2)
    assert rule.id in triggered
    assert triggered[rule.id].trigger is True


@pytest.mark.django_db
def test_evaluator_with_windowed_rule():
    """Test evaluator with windowed rule (accumulating points)"""
    device_type = DeviceType.objects.create(name="Sensor", metric_unit="A")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="3 temps > 20 in 60s",
        condition={
            "type": "leaf",
            "operator": "gt",
            "threshold": 20.0,
            "window_seconds": 60,
            "occurrences": 3,
        },
        action_config=[],
        is_enabled=True,
    )

    evaluator = RealTimeRuleEvaluator()
    t0 = datetime(2026, 2, 16, 12, 0, tzinfo=timezone.utc)

    # Point 1: doesn't trigger (need 3)
    point1 = TelemetryPoint(ts=t0, value=25.0)
    triggered = evaluator.evaluate(device.id, point1)
    assert len(triggered) == 0

    # Point 2: still doesn't trigger
    point2 = TelemetryPoint(ts=t0 + timedelta(seconds=10), value=26.0)
    triggered = evaluator.evaluate(device.id, point2)
    assert len(triggered) == 0

    # Point 3: NOW triggers!
    point3 = TelemetryPoint(ts=t0 + timedelta(seconds=20), value=27.0)
    triggered = evaluator.evaluate(device.id, point3)
    assert rule.id in triggered
    assert triggered[rule.id].trigger is True
    assert len(triggered[rule.id].values) == 3


@pytest.mark.django_db
def test_full_pipeline_mock(mock_producer_consumer, setup_mock_kafka):
    """Test full pipeline: produce telemetry → consume → evaluate → produce events"""
    producer, consumer = mock_producer_consumer

    # Setup rule
    device_type = DeviceType.objects.create(name="Sensor", metric_unit="A")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="Current > 50A",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[],
        is_enabled=True,
    )

    # Setup consumer & evaluator
    consumer.subscribe(["telemetry"])
    evaluator = RealTimeRuleEvaluator()

    # Produce telemetry message
    t0 = datetime.now(timezone.utc)
    telemetry_msg = {
        "device_id": str(device.id),
        "timestamp": t0.isoformat(),
        "source": "mqtt",
        "payload": {"value": 55.0},
    }
    producer.send("telemetry", telemetry_msg)

    # Consume and evaluate
    msg = consumer.poll()
    assert msg is not None

    payload = json.loads(msg.value().decode("utf-8"))
    point = TelemetryPoint(
        ts=datetime.fromisoformat(payload["timestamp"]),
        value=float(payload["payload"]["value"]),
    )

    triggered = evaluator.evaluate(
        device_id=device.id,
        telemetry_point=point,
    )

    # Check results
    assert rule.id in triggered
    assert triggered[rule.id].trigger is True

    # Produce event to Kafka
    event_producer = MockProducer()
    for rule_id, result in triggered.items():
        event_msg = {
            "rule_id": str(rule_id),
            "device_id": str(device.id),
            "timestamp": t0.isoformat(),
            "triggered": True,
            "result": result.to_dict(),
        }
        event_producer.send("events", event_msg)

    # Verify event was produced
    events = get_mock_topic_messages("events")
    assert len(events) == 1
    assert "rule_id" in json.loads(events[0]["value"].decode("utf-8"))


@pytest.mark.django_db
def test_multiple_devices_multiple_rules():
    """Test evaluator with multiple devices and rules"""
    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")

    device1 = Device.objects.create(
        name="Device1", device_type=device_type, serial_number=f"SN-{uuid4().hex[:8]}"
    )
    device2 = Device.objects.create(
        name="Device2", device_type=device_type, serial_number=f"SN-{uuid4().hex[:8]}"
    )

    rule1 = Rule.objects.create(
        device=device1,
        name="Rule1",
        condition={"type": "leaf", "operator": "gt", "threshold": 20.0},
        action_config=[],
        is_enabled=True,
    )

    rule2 = Rule.objects.create(
        device=device1,
        name="Rule2",
        condition={"type": "leaf", "operator": "lt", "threshold": 10.0},
        action_config=[],
        is_enabled=True,
    )

    rule3 = Rule.objects.create(
        device=device2,
        name="Rule3",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[],
        is_enabled=True,
    )

    evaluator = RealTimeRuleEvaluator()

    # Device1 point (triggers rule1, not rule2)
    point1 = TelemetryPoint(ts=datetime.now(timezone.utc), value=25.0)
    triggered1 = evaluator.evaluate(device1.id, point1)
    assert rule1.id in triggered1
    assert rule2.id not in triggered1
    assert rule3.id not in triggered1

    # Device2 point (triggers rule3)
    point2 = TelemetryPoint(ts=datetime.now(timezone.utc), value=55.0)
    triggered2 = evaluator.evaluate(device2.id, point2)
    assert rule3.id in triggered2
    assert rule1.id not in triggered2
    assert rule2.id not in triggered2
