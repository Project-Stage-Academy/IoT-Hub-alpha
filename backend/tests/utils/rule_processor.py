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


def _build_execution_results(rule):
    results = []
    for action in rule.action_config:
        item = {"type": action.get("type"), "status": "pending"}
        if action.get("type") == "notification":
            item["template_id"] = action.get("template_id")
        elif action.get("type") == "stop_machine":
            item["machine_id"] = action.get("machine_id")
        results.append(item)
    return results


def _create_notification_deliveries(event, rule, templates_by_id):
    for action in rule.action_config:
        if action.get("type") != "notification":
            continue
        template = templates_by_id.get(action.get("template_id"))
        if not template:
            continue
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


def _mark_execution_results_completed(execution_results):
    for item in execution_results:
        item["status"] = "completed"
    return execution_results


def process_telemetry_for_device(telemetry):
    device = telemetry.device
    events = []
    rules = Rule.objects.filter(device=device, is_enabled=True)
    for rule in rules:
        result = _rule_matches(rule, telemetry)
        if not result.trigger:
            continue

        execution_results = _build_execution_results(rule)

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

        template_ids = {
            action.get("template_id")
            for action in rule.action_config
            if action.get("type") == "notification"
        }
        templates_by_id = NotificationTemplate.objects.in_bulk(template_ids)
        _create_notification_deliveries(event, rule, templates_by_id)

        event.execution_results = _mark_execution_results_completed(execution_results)
        event.save(update_fields=["execution_results"])

        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at"])
        events.append(event)

    return events
