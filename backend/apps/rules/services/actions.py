import os
import logging
from dataclasses import asdict
from functools import lru_cache
from django.utils import timezone
from datetime import timedelta
from apps.notifications.models import NotificationTemplate
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

    for recipient in notif_template.recipients:
        recipient_clean = NormalizedRecipient.model_validate(recipient)  # noqa: F841
        # Add notification task here
        logger.info(
            "rules.notification.enqueue",
            extra={"event_id": str(event), "rule_id": str(rule)},
        )


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

    new_event = Event(
        timestamp=timezone.now(),
        severity=notif_template.priority,
        message=message,
        execution_results={"status": "new"},
        rule=rule,
        telemetry_snapshot=aggregate.to_dict(),
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
