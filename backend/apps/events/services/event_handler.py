"""Event creation with cooldown protection."""

import os
from datetime import timedelta

from django.utils import timezone

from apps.events.models import Event
from apps.notifications.models import NotificationTemplate

COOLDOWN_TIMER_MINUTES = int(os.getenv("COOLDOWN_TIMER_MINUTES", "60"))


class EventCooldownActive(Exception):
    """Event is in cooldown period and should not be created."""

    pass


def event_handler(aggregate, rule, message: str, template=None):
    """
    Create Event with cooldown protection.

    Checks if rule has active cooldown period. If cooldown is active,
    raises EventCooldownActive. Otherwise, creates Event record and
    returns it.

    Args:
        aggregate: EvalResults with trigger, values, start, end ts
        rule: Rule object that triggered
        message: Event message (e.g., "Rule 'High Temp' triggered")
        template: NotificationTemplate (optional, for future use)

    Returns:
        Event instance created or retrieved from database

    Raises:
        EventCooldownActive: If rule has event cooldown active
    """
    if rule.event_cooldown_until and rule.event_cooldown_until > timezone.now():
        raise EventCooldownActive(
            f"Rule {rule.id} is in cooldown until {rule.event_cooldown_until}"
        )

    event = Event.objects.create(
        rule=rule,
        timestamp=timezone.now(),
        message=message,
        severity=Event.Severity.WARNING,
        status=Event.EventStatus.NEW,
        execution_results=[],
        telemetry_snapshot={
            "values": aggregate.values,
            "start": aggregate.start.isoformat() if aggregate.start else None,
            "end": aggregate.end.isoformat() if aggregate.end else None,
        },
    )

    rule.event_cooldown_until = timezone.now() + timedelta(
        minutes=COOLDOWN_TIMER_MINUTES
    )
    rule.save(update_fields=["event_cooldown_until"])

    return event


def get_template(template_id: int):
    """Get notification template by ID with caching."""
    return NotificationTemplate.objects.get(id=template_id)
