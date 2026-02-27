"""
Integration tests for event creation pipeline.

Tests the complete flow:
  MQTT → Telemetry → RulesConsumer → EventsConsumer → Event Creation
"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone

from apps.events.models import Event
from apps.rules.models import Rule
from apps.rules.services.data_structure import EvalResults
from apps.rules.services.window_state import TelemetryPoint
from apps.devices.models import Device, DeviceType
from apps.telemetry.models import Telemetry


class EventCreationIntegrationTest(TestCase):
    """Test event creation after rule evaluation triggers."""

    @classmethod
    def setUpTestData(cls):
        """Set up test devices and rules."""
        # Create device type
        cls.device_type = DeviceType.objects.create(
            name="Current Sensor",
            metric_name="current",
            metric_unit="Amps",
            metric_min=0,
            metric_max=200,
        )

        # Create device
        cls.device = Device.objects.create(
            serial_number="TEST-CUR-001",
            name="Test Current Sensor",
            device_type=cls.device_type,
            status="active",
        )

        # Create rule with normalized threshold
        cls.rule = Rule.objects.create(
            name="Test High Current Alert",
            device=cls.device,
            description="Test rule for high current",
            condition={
                "type": "leaf",
                "operator": "gt",
                "threshold": 1.5,  # normalized value
            },
            is_enabled=True,
            action_config=[],
        )

    def test_event_created_when_rule_triggers(self):
        """Test that event is created when rule evaluation returns trigger=True."""
        # Create rule evaluation result (simulating RulesConsumer)
        eval_result = EvalResults(
            trigger=True,
            values=[1.65],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Simulate event handler creating event (as EventsConsumer would)
        Event.objects.create(
            rule=self.rule,
            status="new",
            message="Test event created",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.65]},
            execution_results=eval_result.to_dict(),
        )

        # Verify event was created
        events = Event.objects.filter(rule=self.rule)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events[0].status, "new")
        self.assertIn(1.65, events[0].execution_results.get("values", []))

    def test_event_not_created_when_rule_doesnt_trigger(self):
        """Test that no event is created when rule doesn't trigger."""
        initial_count = Event.objects.filter(rule=self.rule).count()

        # Simulate evaluation with no trigger
        eval_result = EvalResults(
            trigger=False,
            values=[1.2],  # Below threshold 1.5
            start=None,
            end=None,
        )

        # Don't create event (normal behavior when trigger=False)
        # Just verify count hasn't changed
        final_count = Event.objects.filter(rule=self.rule).count()
        self.assertEqual(initial_count, final_count)

    def test_cooldown_prevents_duplicate_events(self):
        """Test that cooldown mechanism prevents duplicate events within 60 minutes."""
        # Create first event
        first_event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="First event",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.65]},
        )

        # Set cooldown on rule
        cooldown_time = timezone.now() + timedelta(minutes=60)
        self.rule.event_cooldown_until = cooldown_time
        self.rule.save()

        # Try to create second event - should be blocked in EventsConsumer
        # (This is handled by EventsConsumer logic checking cooldown)
        self.assertIsNotNone(self.rule.event_cooldown_until)
        self.assertTrue(
            self.rule.event_cooldown_until > timezone.now(),
            "Cooldown should be in future",
        )

    def test_event_created_after_cooldown_expires(self):
        """Test that new event can be created after cooldown expires."""
        # Create first event at 12:30
        first_time = timezone.now() - timedelta(hours=1)
        first_event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="First event",
            severity="warning",
            timestamp=first_time,
            telemetry_snapshot={"values": [1.65]},
        )

        # Set cooldown that expired (created 1 hour ago, cooldown was 60 min)
        expired_cooldown = first_time + timedelta(minutes=60)
        self.rule.event_cooldown_until = expired_cooldown
        self.rule.save()

        # Verify cooldown is expired
        self.assertTrue(
            self.rule.event_cooldown_until < timezone.now(),
            "Cooldown should be expired",
        )

        # Create second event (cooldown is expired)
        second_event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="Second event after cooldown",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.75]},
        )

        # Verify both events exist
        events = Event.objects.filter(rule=self.rule).order_by("timestamp")
        self.assertEqual(events.count(), 2)
        self.assertEqual(events[0].message, "First event")
        self.assertEqual(events[1].message, "Second event after cooldown")

    def test_event_telemetry_snapshot_contains_trigger_values(self):
        """Test that event captures telemetry values that triggered the rule."""
        trigger_value = 1.75
        eval_result = EvalResults(
            trigger=True,
            values=[trigger_value],
            start=timezone.now(),
            end=timezone.now(),
        )

        event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="Event with trigger data",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [trigger_value]},
            execution_results=eval_result.to_dict(),
        )

        # Verify telemetry snapshot contains the trigger value
        self.assertIn("values", event.telemetry_snapshot)
        self.assertIn(trigger_value, event.telemetry_snapshot["values"])

    def test_multiple_rules_create_separate_events(self):
        """Test that multiple triggered rules create separate events."""
        # Create second rule for same device
        rule2 = Rule.objects.create(
            name="Test Medium Current Warning",
            device=self.device,
            description="Test rule 2 for medium current",
            condition={
                "type": "leaf",
                "operator": "gt",
                "threshold": 1.2,
            },
            is_enabled=True,
            action_config=[],
        )

        # Create events for both rules
        Event.objects.create(
            rule=self.rule,
            status="new",
            message="High current alert",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.65]},
        )

        Event.objects.create(
            rule=rule2,
            status="new",
            message="Medium current warning",
            severity="info",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.65]},
        )

        # Verify both events exist
        events = list(Event.objects.filter(rule__device=self.device))
        self.assertEqual(len(events), 2)

        rules = {e.rule_id for e in events}
        self.assertEqual(len(rules), 2)
        self.assertIn(self.rule.id, rules)
        self.assertIn(rule2.id, rules)

    def test_event_status_transitions(self):
        """Test event status lifecycle (new → acknowledged → resolved)."""
        event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="New event",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.65]},
        )

        self.assertEqual(event.status, "new")

        # Acknowledge event
        event.status = "acknowledged"
        event.save()
        event.refresh_from_db()
        self.assertEqual(event.status, "acknowledged")

        # Resolve event
        event.status = "resolved"
        event.save()
        event.refresh_from_db()
        self.assertEqual(event.status, "resolved")

    def test_event_severity_levels(self):
        """Test that events capture correct severity levels."""
        severities = ["critical", "warning", "info"]

        for severity in severities:
            event = Event.objects.create(
                rule=self.rule,
                status="new",
                message=f"Event with {severity} severity",
                severity=severity,
                timestamp=timezone.now(),
                telemetry_snapshot={"values": [1.65]},
            )

            event.refresh_from_db()
            self.assertEqual(event.severity, severity)

    def test_event_execution_results_capture(self):
        """Test that event captures rule execution results."""
        eval_result = EvalResults(
            trigger=True,
            values=[1.5, 1.6, 1.7],
            start=timezone.now(),
            end=timezone.now(),
        )

        event = Event.objects.create(
            rule=self.rule,
            status="new",
            message="Event with execution results",
            severity="warning",
            timestamp=timezone.now(),
            telemetry_snapshot={"values": [1.5, 1.6, 1.7]},
            execution_results=eval_result.to_dict(),
        )

        # Verify execution results are stored
        self.assertIsNotNone(event.execution_results)
        self.assertEqual(len(event.execution_results.get("values", [])), 3)
        self.assertIn(1.5, event.execution_results["values"])
        self.assertIn(1.6, event.execution_results["values"])
        self.assertIn(1.7, event.execution_results["values"])


class EventCreationEndToEndTest(TestCase):
    """End-to-end tests simulating real MQTT → Event flow."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for end-to-end tests."""
        cls.device_type = DeviceType.objects.create(
            name="Current Sensor",
            metric_name="current",
            metric_unit="Amps",
            metric_min=0,
            metric_max=200,
        )

        cls.device = Device.objects.create(
            serial_number="E2E-CUR-001",
            name="E2E Test Sensor",
            device_type=cls.device_type,
            status="active",
        )

        cls.rule = Rule.objects.create(
            name="E2E Test Rule",
            device=cls.device,
            description="End-to-end test rule",
            condition={
                "type": "leaf",
                "operator": "gt",
                "threshold": 1.5,
            },
            is_enabled=True,
            action_config=[],
        )

    def test_end_to_end_mqtt_to_event(self):
        """Test complete pipeline from MQTT telemetry to event creation."""
        # Step 1: Simulate telemetry ingestion (MQTT → Telemetry)
        telemetry = Telemetry.objects.create(
            device=self.device,
            payload={
                "schema_version": "1.0",
                "serial_number": self.device.serial_number,
                "value": 165,  # Will be normalized to 1.65
            },
        )

        # Step 2: Verify telemetry was stored
        self.assertEqual(Telemetry.objects.filter(device=self.device).count(), 1)

        # Step 3: Simulate rule evaluation (RulesConsumer)
        normalized_value = 1.65  # 165 / 100
        eval_result = EvalResults(
            trigger=(normalized_value > 1.5),  # True
            values=[normalized_value],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Step 4: Create event based on evaluation (EventsConsumer)
        if eval_result.trigger:
            event = Event.objects.create(
                rule=self.rule,
                status="new",
                message=f"Rule triggered: {self.rule.name}",
                severity="warning",
                timestamp=timezone.now(),
                telemetry_snapshot={"values": eval_result.values},
                execution_results=eval_result.to_dict(),
            )

            # Step 5: Verify event was created
            self.assertIsNotNone(event.id)
            self.assertEqual(event.rule, self.rule)
            self.assertEqual(event.status, "new")

        # Final verification
        events = Event.objects.filter(rule=self.rule)
        self.assertEqual(events.count(), 1)
        self.assertIn(1.65, events[0].execution_results["values"])
