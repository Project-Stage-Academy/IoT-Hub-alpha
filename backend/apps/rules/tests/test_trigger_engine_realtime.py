"""
Tests for real-time trigger engine (Kafka dispatch).
"""

import pytest
import json
from datetime import datetime, timezone
from uuid import uuid4

from apps.rules.models import Rule
from apps.rules.services.data_structure import EvalResults
from apps.rules.services.trigger_engine import trigger_engine_realtime
from apps.telemetry.mocks.kafka import (
    MockProducer,
    reset_mock_topics,
    get_mock_topic_messages,
)
from apps.devices.models import Device, DeviceType


@pytest.mark.django_db
def test_trigger_engine_realtime_sends_event_to_kafka():
    """Test that trigger_engine_realtime sends event to Kafka events topic"""
    # Setup
    reset_mock_topics()
    producer = MockProducer()

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="Temperature > 30°C",
        condition={"type": "leaf", "operator": "gt", "threshold": 30.0},
        action_config=[],
        is_enabled=True,
    )

    # Create evaluation result
    now = datetime.now(timezone.utc)
    eval_result = EvalResults(trigger=True, values=[35.0], start=now, end=now)

    # Execute
    trigger_engine_realtime(rule.id, device.id, eval_result, producer)

    # Verify event in Kafka
    events = get_mock_topic_messages("events")
    assert len(events) == 1, "Should have 1 event in events topic"

    event_data = json.loads(events[0]["value"].decode("utf-8"))
    assert event_data["rule_id"] == str(rule.id)
    assert event_data["device_id"] == str(device.id)
    assert event_data["message"] == f"Rule '{rule.name}' triggered"
    assert event_data["severity"] == "warning"
    assert event_data["telemetry_snapshot"]["values"] == [35.0]


@pytest.mark.django_db
def test_trigger_engine_realtime_with_missing_rule():
    """Test that missing rule is handled gracefully"""
    reset_mock_topics()
    producer = MockProducer()

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    now = datetime.now(timezone.utc)
    eval_result = EvalResults(trigger=True, values=[35.0], start=now, end=now)

    fake_rule_id = uuid4()

    # Execute (should not crash)
    trigger_engine_realtime(fake_rule_id, device.id, eval_result, producer)

    # Verify no event sent
    events = get_mock_topic_messages("events")
    assert len(events) == 0, "Should have no events (rule not found)"


@pytest.mark.django_db
def test_trigger_engine_realtime_event_message_structure():
    """Test that event message has correct structure"""
    reset_mock_topics()
    producer = MockProducer()

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="A")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="High Current",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[],
        is_enabled=True,
    )

    now = datetime.now(timezone.utc)
    eval_result = EvalResults(
        trigger=True, values=[55.0, 60.0], start=now, end=now
    )

    trigger_engine_realtime(rule.id, device.id, eval_result, producer)

    events = get_mock_topic_messages("events")
    event_data = json.loads(events[0]["value"].decode("utf-8"))

    # Verify all required fields
    assert "rule_id" in event_data
    assert "device_id" in event_data
    assert "timestamp" in event_data
    assert "severity" in event_data
    assert "message" in event_data
    assert "execution_results" in event_data
    assert "telemetry_snapshot" in event_data

    # Verify types
    assert isinstance(event_data["rule_id"], str)
    assert isinstance(event_data["device_id"], str)
    assert isinstance(event_data["severity"], str)
    assert isinstance(event_data["execution_results"], list)
    assert isinstance(event_data["telemetry_snapshot"], dict)


@pytest.mark.django_db
def test_trigger_engine_realtime_multiple_triggers():
    """Test multiple rules triggering and sending to Kafka"""
    reset_mock_topics()
    producer = MockProducer()

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule1 = Rule.objects.create(
        device=device,
        name="Temp > 30",
        condition={"type": "leaf", "operator": "gt", "threshold": 30.0},
        action_config=[],
        is_enabled=True,
    )

    rule2 = Rule.objects.create(
        device=device,
        name="Temp > 35",
        condition={"type": "leaf", "operator": "gt", "threshold": 35.0},
        action_config=[],
        is_enabled=True,
    )

    now = datetime.now(timezone.utc)
    eval_result1 = EvalResults(trigger=True, values=[35.0], start=now, end=now)
    eval_result2 = EvalResults(trigger=True, values=[38.0], start=now, end=now)

    # Dispatch both
    trigger_engine_realtime(rule1.id, device.id, eval_result1, producer)
    trigger_engine_realtime(rule2.id, device.id, eval_result2, producer)

    # Verify both in Kafka
    events = get_mock_topic_messages("events")
    assert len(events) == 2, "Should have 2 events"

    rule_ids = set()
    for event in events:
        data = json.loads(event["value"].decode("utf-8"))
        rule_ids.add(data["rule_id"])

    assert str(rule1.id) in rule_ids
    assert str(rule2.id) in rule_ids


@pytest.mark.django_db
def test_trigger_engine_realtime_timestamp_handling():
    """Test different timestamp scenarios"""
    reset_mock_topics()
    producer = MockProducer()

    device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
    device = Device.objects.create(name="TestDevice", device_type=device_type)

    rule = Rule.objects.create(
        device=device,
        name="Test Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 20.0},
        action_config=[],
        is_enabled=True,
    )

    now = datetime.now(timezone.utc)

    # Case 1: Both start and end present
    eval_result = EvalResults(trigger=True, values=[25.0], start=now, end=now)
    trigger_engine_realtime(rule.id, device.id, eval_result, producer)

    events = get_mock_topic_messages("events")
    assert len(events) >= 1
    event_data = json.loads(events[-1]["value"].decode("utf-8"))
    assert event_data["timestamp"] is not None
    assert event_data["timestamp"] == now.isoformat()
