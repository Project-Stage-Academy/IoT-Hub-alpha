from __future__ import annotations
import pytest
from unittest.mock import Mock, patch
from apps.events.models import Event
from apps.notifications.models import NotificationPriority
from apps.events.services.actions import (
    action_dispatch,
    dispatch_msg,
)
from apps.events.services.event_handler import (
    event_handler,
    EventCooldownActive,
)
from apps.rules.services.data_structure import ActionConfig, EvalResults


def test_action_dispatch_calls_notification_dispatch():
    """
    Test notification being called by action_dispatch
    """
    cfg = ActionConfig.model_validate({"type": "notification", "template_id": 1})
    rule = object()
    agg = EvalResults(trigger=True, values=[123.0])
    event = Mock(spec=Event)

    with patch("apps.events.services.actions.dispatch_msg") as mock_dispatch:
        action_dispatch(cfg, rule, agg, event)

    mock_dispatch.assert_called_once_with(cfg, rule, agg, event)


def test_action_dispatch_calls_stop_machine():
    """
    Tests stop machine stub
    """
    cfg = ActionConfig.model_validate({"type": "stop_machine"})
    rule = object()
    agg = EvalResults(trigger=True, values=[123.0])
    event = Mock(spec=Event)

    with patch("apps.events.services.actions.stop_machine") as mock_stop:
        action_dispatch(cfg, rule, agg, event)

    mock_stop.assert_called_once_with(cfg, rule, agg, event)


def test_action_dispatch_unknown_type_is_noop():
    """
    Tests unknown type doesnt go through
    """

    class Dummy:
        type = "unknown"

    event = Mock(spec=Event)
    with patch("apps.events.services.actions.dispatch_msg") as mock_dispatch:
        action_dispatch(Dummy(), object(), EvalResults(trigger=True, values=[1.0]), event)  # type: ignore[arg-type]

    mock_dispatch.assert_not_called()


def test_dispatch_msg_formats_message_and_enqueues_notifications():
    """
    test correct msg formatting and notification enqueue call
    """
    cfg = ActionConfig.model_validate({"type": "notification", "template_id": 1})

    class DummyDeviceType:
        metric_unit = "C"

    class DummyDevice:
        name = "Device-01"
        device_type = DummyDeviceType()

    class DummyRule:
        device = DummyDevice()

    rule = DummyRule()
    agg = EvalResults(trigger=True, values=[10.0, 42.0])

    class DummyTemplate:
        id = 1
        priority = 2
        message_template = "{severity} {device_name} {value}{unit}"
        recipients = [{"type": "email", "address": "a@b.com"}]

        def get_priority_display(self):
            return "HIGH"

    event = Mock(spec=Event)
    event.id = 123

    with (
        patch(
            "apps.events.services.actions.get_template", return_value=DummyTemplate()
        ) as mock_get_template,
        patch(
            "apps.notifications.tasks.enqueue_notification_deliveries",
            return_value=[Mock(), Mock()],
        ) as mock_enqueue,
    ):
        dispatch_msg(cfg, rule, agg, event)

    mock_get_template.assert_called_once_with(tid=1)
    mock_enqueue.assert_called_once()
    assert event.save.called


def test_dispatch_msg_returns_if_no_event():
    """
    Test dispatch_msg returns early if no event object
    """
    cfg = ActionConfig.model_validate({"type": "notification", "template_id": 1})

    class DummyDeviceType:
        metric_unit = "C"

    class DummyDevice:
        name = "Device-01"
        device_type = DummyDeviceType()

    class DummyRule:
        id = "test-rule-id"
        device = DummyDevice()

    rule = DummyRule()
    agg = EvalResults(trigger=True, values=[1.0])

    class DummyTemplate:
        id = 1
        priority = 1
        message_template = "{severity}"
        recipients = [{"type": "email", "address": "a@b.com"}]

        def get_priority_display(self):
            return "LOW"

    with (
        patch(
            "apps.events.services.actions.get_template", return_value=DummyTemplate()
        ),
        patch(
            "apps.events.services.actions.NormalizedRecipient.model_validate"
        ) as mock_validate,
    ):
        dispatch_msg(cfg, rule, agg, event=None)

    mock_validate.assert_not_called()


def test_dispatch_msg_validates_each_recipient():
    """
    test each recipient gets its own msg call
    """
    cfg = ActionConfig.model_validate({"type": "notification", "template_id": 1})

    class DummyDeviceType:
        metric_unit = "C"

    class DummyDevice:
        name = "Device-01"
        device_type = DummyDeviceType()

    class DummyRule:
        device = DummyDevice()

    rule = DummyRule()
    agg = EvalResults(trigger=True, values=[1.0])

    class DummyTemplate:
        id = 1
        priority = 1
        message_template = "{severity}"
        recipients = [
            {"type": "email", "address": "a@b.com"},
            {"type": "sms", "phone": "+3800000000"},
        ]

        def get_priority_display(self):
            return "LOW"

    event = Mock(spec=Event)
    event.id = 456

    with (
        patch(
            "apps.events.services.actions.get_template", return_value=DummyTemplate()
        ),
        patch(
            "apps.notifications.tasks.enqueue_notification_deliveries", return_value=[]
        ),
        patch(
            "apps.events.services.actions.NormalizedRecipient.model_validate"
        ) as mock_validate,
    ):
        dispatch_msg(cfg, rule, agg, event)

    assert mock_validate.call_count == 2


@pytest.mark.django_db
def test_event_handler_creates_event_when_no_recent_events(
    rule_model, notif_template_model
):
    """
    Tests event handler created an event when not on cooldown
    """
    agg = EvalResults(trigger=True, values=[10.0], start=None, end=None)
    msg = "hello world, THIS! IS! TESTINGGGGGGGGGGGG!"

    ev = event_handler(agg, rule_model, msg, notif_template_model)

    assert ev.rule_id == rule_model.id
    assert ev.message == msg
    assert ev.severity == notif_template_model.priority
    assert ev.execution_results == {"status": "new"}
    assert ev.telemetry_snapshot["values"] == agg.values


@pytest.mark.django_db
def test_event_handler_raises_on_cooldown(
    rule_model, notif_template_model, event_model
):
    """
    Event handler raises when on cooldown and silently continues
    """
    agg = EvalResults(trigger=True, values=[10.0])
    with pytest.raises(EventCooldownActive):
        event_handler(agg, rule_model, "msg", notif_template_model)
