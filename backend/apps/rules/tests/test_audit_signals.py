from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.rules.audit import bind_audit_actor, reset_audit_actor
from apps.rules.audit.signals import audit_rule_saved
from apps.devices.models import Device, DeviceType
from apps.rules.audit import TRACKED_RULE_FIELDS
from apps.rules.models import Rule, RuleAuditLog


@pytest.fixture
def device(db):
    device_type = DeviceType.objects.create(name="temp", metric_unit="C")
    return Device.objects.create(
        name="Device-1",
        serial_number="SN-0001",
        device_type=device_type,
    )


def _create_rule(device: Device) -> Rule:
    return Rule.objects.create(
        device=device,
        name="High Temp",
        description="Initial",
        condition={"type": "leaf", "operator": "gt", "threshold": 70.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )


@pytest.mark.django_db(transaction=True)
def test_rule_create_writes_create_audit_log(device):
    RuleAuditLog.objects.all().delete()
    rule = _create_rule(device)

    log = RuleAuditLog.objects.get(rule_id=rule.id)
    assert log.action == RuleAuditLog.Action.CREATE
    assert log.before == {}
    assert set(log.changed_fields) == set(TRACKED_RULE_FIELDS)
    assert set(log.after.keys()) == set(TRACKED_RULE_FIELDS)


@pytest.mark.django_db(transaction=True)
def test_rule_update_writes_exact_diff(device):
    rule = _create_rule(device)
    RuleAuditLog.objects.all().delete()

    rule.name = "High Temp Updated"
    rule.save(update_fields=["name"])

    log = RuleAuditLog.objects.get(rule_id=rule.id)
    assert log.action == RuleAuditLog.Action.UPDATE
    assert log.changed_fields == ["name"]
    assert log.before == {"name": "High Temp"}
    assert log.after == {"name": "High Temp Updated"}


@pytest.mark.django_db(transaction=True)
def test_rule_delete_writes_delete_audit_log(device):
    rule = _create_rule(device)
    RuleAuditLog.objects.all().delete()

    rule_id = rule.id
    rule.delete()

    log = RuleAuditLog.objects.get(rule_id=rule_id)
    assert log.action == RuleAuditLog.Action.DELETE
    assert set(log.changed_fields) == set(TRACKED_RULE_FIELDS)
    assert set(log.before.keys()) == set(TRACKED_RULE_FIELDS)
    assert log.after == {}


@pytest.mark.django_db
def test_rule_noop_save_writes_no_update_log(device):
    rule = _create_rule(device)
    RuleAuditLog.objects.all().delete()

    rule.save()

    assert RuleAuditLog.objects.count() == 0


@pytest.mark.django_db
def test_runtime_field_update_is_ignored(device):
    rule = _create_rule(device)
    RuleAuditLog.objects.all().delete()

    rule.last_triggered_at = timezone.now()
    rule.save(update_fields=["last_triggered_at"])

    assert RuleAuditLog.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_on_commit_keeps_bound_actor_context(device):
    RuleAuditLog.objects.all().delete()
    user = get_user_model().objects.create_user(
        username="audit-admin",
        password="pass-123",
    )

    token = bind_audit_actor(user)
    with transaction.atomic():
        _create_rule(device)
        reset_audit_actor(token)

    log = RuleAuditLog.objects.latest("id")
    assert log.action == RuleAuditLog.Action.CREATE
    assert log.actor_user_id == user.id
    assert log.actor_username == "audit-admin"


@pytest.mark.django_db
def test_post_save_signal_skips_when_raw_true(device):
    rule = _create_rule(device)
    RuleAuditLog.objects.all().delete()

    audit_rule_saved(
        sender=Rule,
        instance=rule,
        created=False,
        raw=True,
    )

    assert RuleAuditLog.objects.count() == 0
