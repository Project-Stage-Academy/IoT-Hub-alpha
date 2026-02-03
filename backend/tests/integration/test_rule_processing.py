import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.notifications.models import NotificationDelivery, NotificationTemplate
from apps.rules.models import Rule


def _rule_matches(rule, payload_value):
    threshold = float(rule.threshold)
    value = float(payload_value)

    if rule.comparison_operator == Rule.RuleOperator.GT:
        return value > threshold
    if rule.comparison_operator == Rule.RuleOperator.GTE:
        return value >= threshold
    if rule.comparison_operator == Rule.RuleOperator.LT:
        return value < threshold
    if rule.comparison_operator == Rule.RuleOperator.LTE:
        return value <= threshold
    if rule.comparison_operator == Rule.RuleOperator.EQ:
        return value == threshold
    if rule.comparison_operator == Rule.RuleOperator.NEQ:
        return value != threshold

    return False


def process_telemetry_for_device(telemetry):
    device = telemetry.device
    value = telemetry.payload.get("value")
    if value is None:
        return []

    events = []
    rules = Rule.objects.filter(device=device, is_enabled=True)
    for rule in rules:
        if not _rule_matches(rule, value):
            continue

        event = Event.objects.create(
            rule=rule,
            severity=Event.EventSeverity.WARNING,
            message=f"Rule '{rule.name}' triggered for {device.name}",
            execution_results=[
                {
                    "type": "notification",
                    "template_id": rule.action_config[0]["template_id"],
                    "status": "pending",
                }
            ],
            telemetry_snapshot={
                "device_id": str(device.id),
                "timestamp": telemetry.timestamp.isoformat(),
                "payload": telemetry.payload,
            },
            status=Event.EventStatus.NEW,
        )

        for action in rule.action_config:
            if action.get("type") != "notification":
                continue
            template = NotificationTemplate.objects.get(id=action["template_id"])
            for recipient in template.recipients:
                if recipient["type"] == "email":
                    address = recipient["address"]
                    notification_type = NotificationDelivery.NotificationType.EMAIL
                elif recipient["type"] == "sms":
                    address = recipient["phone"]
                    notification_type = NotificationDelivery.NotificationType.SMS
                else:
                    address = recipient["url"]
                    notification_type = NotificationDelivery.NotificationType.WEBHOOK

                NotificationDelivery.objects.create(
                    event=event,
                    template=template,
                    notification_type=notification_type,
                    recipient_address=address,
                    rendered_message=template.message_template.format(
                        severity=event.severity, message=event.message
                    ),
                    status=NotificationDelivery.NotificationStatus.PENDING,
                )

        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at"])
        events.append(event)

    return events


@pytest.mark.django_db
def test_integration_flow_triggers_event_and_delivery(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="High Temp Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        comparison_operator=Rule.RuleOperator.GT,
        threshold=50.0,
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert len(events) == 1
    assert Event.objects.count() == 1
    assert NotificationDelivery.objects.count() == 1
    delivery = NotificationDelivery.objects.first()
    assert delivery.status == NotificationDelivery.NotificationStatus.PENDING


@pytest.mark.django_db
def test_integration_flow_no_event_when_threshold_not_met(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="Low Temp Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        comparison_operator=Rule.RuleOperator.GT,
        threshold=50.0,
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 45.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert events == []
    assert Event.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_integration_flow_no_event_when_rule_disabled(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="Disabled Rule Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="Disabled Rule",
        comparison_operator=Rule.RuleOperator.GT,
        threshold=50.0,
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=False,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert events == []
    assert Event.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_integration_flow_multiple_recipients_create_multiple_deliveries(
    device, telemetry_factory
):
    template = NotificationTemplate.objects.create(
        name="Multi Recipient Alert",
        message_template="Alert {severity}: {message}",
        recipients=[
            {"type": "email", "address": "alerts@example.com"},
            {"type": "sms", "phone": "+15550001111"},
        ],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        comparison_operator=Rule.RuleOperator.GT,
        threshold=50.0,
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert len(events) == 1
    assert Event.objects.count() == 1
    assert NotificationDelivery.objects.count() == 2
