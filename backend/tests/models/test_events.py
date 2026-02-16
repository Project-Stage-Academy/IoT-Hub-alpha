import pytest
from django.core.exceptions import ValidationError

from apps.events.models import Event


@pytest.mark.django_db
def test_create_event(event, rule):
    assert event.pk is not None
    assert event.rule == rule
    assert event.status == Event.EventStatus.NEW
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_event_str(event):
    text = str(event)
    assert str(event.id) in text
    assert str(event.rule_id) in text
    assert event.severity in text


@pytest.mark.django_db
def test_event_execution_results_validation_requires_fields(rule):
    event = Event(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="Bad results",
        execution_results=[{"status": "completed"}],
    )

    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "execution_results",
    [
        "not-a-list",
        ["not-a-dict"],
        [{"type": "notification", "template_id": 1}],
        [{"status": "completed"}],
        [{"type": "notification", "status": "completed"}],
        [{"type": "stop_machine", "status": "completed"}],
    ],
)
def test_event_execution_results_validation_rejects_invalid_structures(
    rule, execution_results
):
    event = Event(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="Bad results",
        execution_results=execution_results,
    )

    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
def test_event_telemetry_snapshot_validation_requires_payload(rule):
    event = Event(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="Missing payload",
        execution_results=[
            {"type": "notification", "template_id": 1, "status": "completed"}
        ],
        telemetry_snapshot={"device_id": "abc", "timestamp": "2026-01-01T00:00:00Z"},
    )

    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
def test_event_telemetry_snapshot_allows_none(rule):
    event = Event(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="No snapshot",
        execution_results=[
            {"type": "notification", "template_id": 1, "status": "completed"}
        ],
        telemetry_snapshot=None,
    )

    event.full_clean()


@pytest.mark.django_db
def test_event_telemetry_snapshot_rejects_non_object(rule):
    event = Event(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="Bad snapshot",
        execution_results=[
            {"type": "notification", "template_id": 1, "status": "completed"}
        ],
        telemetry_snapshot="not-an-object",
    )

    with pytest.raises(ValidationError):
        event.full_clean()


@pytest.mark.django_db
def test_event_deleted_when_rule_deleted(event, rule):
    rule.delete()

    assert Event.objects.count() == 0
