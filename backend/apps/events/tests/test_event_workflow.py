"""Integration tests for event workflow from rule trigger to action dispatch."""

import pytest
from django.utils import timezone
from datetime import timedelta

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.events.services.event_handler import event_handler, EventCooldownActive
from apps.events.services.actions import action_dispatch, dispatch_msg, stop_machine
from apps.notifications.models import NotificationTemplate
from apps.rules.models import Rule
from apps.rules.services.data_structure import ActionConfig, EvalResults


@pytest.mark.django_db
class TestEventWorkflow:
    """Test complete event creation workflow."""

    def setup_method(self):
        """Setup test dependencies for each test."""
        self.device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        self.device = Device.objects.create(
            name="Temperature Sensor",
            serial_number="SENSOR-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="High Temperature Alert",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[{"type": "notification", "template_id": 1}],
        )
        self.template = NotificationTemplate.objects.create(
            name="Alert Template",
            priority=2,
            message_template="Alert: {rule_name}",
            recipients=[{"type": "email", "address": "alert@example.com"}],
        )

    def test_event_creation_on_rule_trigger(self):
        """Event is created when rule is triggered."""
        aggregate = EvalResults(
            trigger=True,
            values=[26.0, 27.0],
            start=timezone.now() - timedelta(seconds=10),
            end=timezone.now(),
        )

        event = event_handler(aggregate, self.rule, "Temperature exceeded 25°C")

        assert event is not None
        assert event.rule_id == self.rule.id
        assert event.message == "Temperature exceeded 25°C"
        assert event.severity == Event.EventSeverity.WARNING
        assert event.status == Event.EventStatus.NEW

    def test_event_stores_telemetry_snapshot(self):
        """Event stores telemetry snapshot for later analysis."""
        start = timezone.now() - timedelta(minutes=1)
        end = timezone.now()
        aggregate = EvalResults(
            trigger=True,
            values=[24.5, 25.5, 26.5],
            start=start,
            end=end,
        )

        event = event_handler(aggregate, self.rule, "Test event")

        assert event.telemetry_snapshot is not None
        assert event.telemetry_snapshot["values"] == [24.5, 25.5, 26.5]
        assert event.telemetry_snapshot["start"] == start.isoformat()
        assert event.telemetry_snapshot["end"] == end.isoformat()

    def test_cooldown_prevents_event_spam(self):
        """Cooldown mechanism prevents creating too many events."""
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # First event should succeed
        event1 = event_handler(aggregate, self.rule, "First alert")
        assert event1 is not None

        # Immediately trying again should fail
        with pytest.raises(EventCooldownActive):
            event_handler(aggregate, self.rule, "Second alert")

    def test_cooldown_expires_after_timeout(self):
        """New events can be created after cooldown expires."""
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Create first event
        event1 = event_handler(aggregate, self.rule, "Alert 1")
        assert event1 is not None

        # Manually expire cooldown
        self.rule.refresh_from_db()
        self.rule.event_cooldown_until = timezone.now() - timedelta(minutes=1)
        self.rule.save()

        # Should now be able to create another event
        event2 = event_handler(aggregate, self.rule, "Alert 2")
        assert event2 is not None
        assert event1.id != event2.id

    def test_notification_action_dispatches_successfully(self):
        """Notification action finds template and dispatches."""
        config = ActionConfig(type="notification", template_id=self.template.id)
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should not raise exception
        dispatch_msg(config, self.rule, aggregate)

    def test_notification_action_fails_for_missing_template(self):
        """Notification action raises for missing template."""
        config = ActionConfig(type="notification", template_id=99999)
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        with pytest.raises(NotificationTemplate.DoesNotExist):
            dispatch_msg(config, self.rule, aggregate)

    def test_stop_machine_action_dispatches(self):
        """Stop machine action logs and completes successfully."""
        config = ActionConfig(type="stop_machine")
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should not raise exception
        stop_machine(config, self.rule, aggregate)

    def test_action_dispatch_routes_notification_type(self):
        """action_dispatch routes to dispatch_msg for notification type."""
        config = ActionConfig(type="notification", template_id=self.template.id)
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should complete without exception
        action_dispatch(config, self.rule, aggregate)

    def test_action_dispatch_routes_stop_machine_type(self):
        """action_dispatch routes to stop_machine for stop_machine type."""
        config = ActionConfig(type="stop_machine")
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should complete without exception
        action_dispatch(config, self.rule, aggregate)

    def test_action_dispatch_handles_unknown_type_gracefully(self):
        """action_dispatch logs unknown action type gracefully."""
        from unittest.mock import MagicMock

        config = MagicMock()
        config.type = "unknown_action_type"
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should not raise exception
        action_dispatch(config, self.rule, aggregate)

    def test_action_dispatch_handles_dispatch_errors_gracefully(self):
        """action_dispatch handles exceptions in action handlers gracefully."""
        config = ActionConfig(type="notification", template_id=99999)
        aggregate = EvalResults(
            trigger=True,
            values=[26.0],
            start=timezone.now(),
            end=timezone.now(),
        )

        # Should not raise exception (error is caught and logged)
        action_dispatch(config, self.rule, aggregate)

    def test_full_workflow_event_creation_and_action(self):
        """Test complete workflow: trigger event and dispatch action."""
        # Simulate rule trigger
        aggregate = EvalResults(
            trigger=True,
            values=[26.0, 27.0],
            start=timezone.now() - timedelta(seconds=30),
            end=timezone.now(),
        )

        # Create event
        event = event_handler(aggregate, self.rule, "High temperature detected")
        assert event is not None

        # Dispatch associated action
        for action in self.rule.action_config:
            config = ActionConfig.model_validate(action)
            # Should not raise
            action_dispatch(config, self.rule, aggregate)

        # Verify event in database
        db_event = Event.objects.get(id=event.id)
        assert db_event.rule_id == self.rule.id
        assert db_event.message == "High temperature detected"
