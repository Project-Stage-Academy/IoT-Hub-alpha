from django.utils import timezone

from apps.events.models import Event
from apps.notifications.models import NotificationDelivery, NotificationTemplate
from apps.rules.models import Rule
from apps.rules.services.data_structure import Condition, EvalResults
from apps.rules.services.rule_eval import eval_rule, TelemetryPoint


def _rule_matches(rule, telemetry):
    value = telemetry.payload.get("value")
    if value is None:
        return EvalResults()

    condition = Condition.model_validate(rule.condition)
    points = [TelemetryPoint(ts=telemetry.timestamp, value=float(value))]
    return eval_rule(condition, points, EvalResults(), rule.device_id)


def process_telemetry_for_device(telemetry):
    device = telemetry.device
    events = []
    rules = Rule.objects.filter(device=device, is_enabled=True)
    for rule in rules:
        result = _rule_matches(rule, telemetry)
        if not result.trigger:
            continue

        execution_results = []
        for action in rule.action_config:
            item = {"type": action.get("type"), "status": "pending"}
            if action.get("type") == "notification":
                item["template_id"] = action.get("template_id")
            elif action.get("type") == "stop_machine":
                item["machine_id"] = action.get("machine_id")
            execution_results.append(item)

        event = Event.objects.create(
            rule=rule,
            severity=Event.EventSeverity.WARNING,
            message=f"Rule '{rule.name}' triggered for {device.name}",
            execution_results=execution_results,
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
