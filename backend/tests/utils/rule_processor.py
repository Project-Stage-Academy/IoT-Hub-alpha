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
