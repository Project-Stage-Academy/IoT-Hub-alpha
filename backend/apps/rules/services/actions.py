import os
import logging
from dataclasses import asdict
from functools import lru_cache
from django.utils import timezone
from datetime import timedelta
from apps.notifications.models import NotificationTemplate, NotificationPriority
from .data_structure import ActionConfig
from apps.events.models import Event
from apps.rules.models import Rule
from apps.rules.services.data_structure import NormalizedRecipient, EvalResults

COOLDOWN_TIMER_MINUTES = os.getenv("DJANGO_RULE_COOLDOWN_MINUTES", 60)

logger = logging.getLogger("apps.rules")


class EventCooldownActive(Exception):
    """Event already exists within cooldown window."""


def action_dispatch(
    action_config: ActionConfig, rule: Rule, aggregate: EvalResults
) -> None:
    """
    Dispatch types of action config
    either machine_stop or notifications

    :param action_config: Description
    :type action_config: ActionConfig
    :param rule: Description
    :type rule: Rule
    :param aggregate: Description
    :type aggregate: AggregateStructure
    """
    action_map = {
        "notification": dispatch_msg,
        "stop_machine": stop_machine,
    }

    action = action_map.get(action_config.type)
    if action:
        action(action_config, rule, aggregate)

    # Write to Events if successful


def dispatch_msg(
    action_config: ActionConfig, rule: Rule, aggregate: EvalResults
) -> None:
    """
    Handle event creation, message formatting and dispatch to actual
    notification stubs

    :param action_config: Description
    :type action_config: ActionConfig
    :param rule: Description
    :type rule: Rule
    :param aggregate: Description
    :type aggregate: AggregateStructure
    """
    notif_template = get_template(tid=action_config.template_id)

    template = notif_template.message_template

    message = template.format(
        severity=notif_template.get_priority_display(),
        device_name=rule.device.name,
        value=max(aggregate.values),
        unit=rule.device.device_type.metric_unit,
    )
    try:
        event = event_handler(aggregate, rule, message, notif_template)  # noqa: F841
    except EventCooldownActive:
        return

    recipients = []
    for recipient in notif_template.recipients:
        recipient_clean = NormalizedRecipient.model_validate(recipient)
        recipients.append(recipient_clean)

    try:
        from apps.notifications.tasks import enqueue_notification_deliveries
    except Exception as exc:  # noqa: BLE001 - best effort enqueue
        logger.warning(
            "rules.notification.enqueue_failed",
            extra={"event_id": event.id, "error": str(exc)},
        )
        return

    deliveries = enqueue_notification_deliveries(
        event=event,
        template=notif_template,
        recipients=recipients,
        rendered_message=message,
    )

    event.execution_results = [
        {
            "type": "notification",
            "template_id": notif_template.id,
            "status": "queued",
            "recipient_count": len(deliveries),
        }
    ]
    event.save(update_fields=["execution_results"])

    return


def stop_machine(action_config, rule, aggregate):
    """
    stop machine stub

    :param action_config: Description
    :param rule: Description
    :param aggregate: Description
    """
    print("Stop machine stub")


def event_handler(
    aggregate: EvalResults,
    rule: Rule,
    message: str,
    notif_template: NotificationTemplate,
) -> Event:
    """
    handles event creation or retrieval based on a cooldown
    to avoid duplicate notifications.

    :param aggregate: Description
    :type aggregate: AggregateStructure
    :param rule: Description
    :type rule: Rule
    :param message: Description
    :type message: str
    :param notif_template: Description
    :type notif_template: NotificationTemplate
    :return: Description
    :rtype: Event
    """

    cooldown_timer = timezone.now() - timedelta(minutes=int(COOLDOWN_TIMER_MINUTES))

    event_exists = (
        Event.objects.filter(rule=rule, timestamp__gte=cooldown_timer)
        .exclude(status=Event.EventStatus.RESOLVED)
        .exists()
    )

    if event_exists:
        logger.info(
            "Event exsits and is on cooldown",
            extra={
                "event": {
                    "message": "Event raised but cooldown is active, "
                    "no additional events triggered",
                    "triggering telemetry": f"values: {aggregate.values} "
                    f"start: {aggregate.start}",
                }
            },
        )
        raise EventCooldownActive

    snapshot = {
        "device_id": str(rule.device_id),
        "timestamp": (
            aggregate.end.isoformat() if aggregate.end else timezone.now().isoformat()
        ),
        "payload": {
            "values": aggregate.values,
            "start": aggregate.start.isoformat() if aggregate.start else None,
            "end": aggregate.end.isoformat() if aggregate.end else None,
        },
    }
    priority_map = {
        NotificationPriority.LOW: Event.EventSeverity.INFO,
        NotificationPriority.MEDIUM: Event.EventSeverity.WARNING,
        NotificationPriority.HIGH: Event.EventSeverity.CRITICAL,
        NotificationPriority.CRITICAL: Event.EventSeverity.CRITICAL,
    }
    severity = priority_map.get(notif_template.priority, Event.EventSeverity.INFO)

    new_event = Event(
        timestamp=timezone.now(),
        severity=severity,
        message=message,
        execution_results=[],
        rule=rule,
        telemetry_snapshot=snapshot,
    )
    new_event.save()
    return new_event


@lru_cache(maxsize=256)
def get_template(tid: int) -> NotificationTemplate:
    """
    get notification template using LRU cache

    :param tid: Description
    :type tid: int
    :return: Description
    :rtype: NotificationTemplate
    """
    return NotificationTemplate.objects.get(id=tid)
