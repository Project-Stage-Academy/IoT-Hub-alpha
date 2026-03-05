from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.devices.models import Device, DeviceType
from apps.rules.admin import disable_rules, enable_rules
from apps.rules.models import Rule, RuleAuditLog


class _DummyModelAdmin:
    def message_user(self, request, message, level=None):
        return None


@pytest.fixture
def admin_request(db):
    user = get_user_model().objects.create_user(
        username="admin-operator",
        password="pass-123",
        email="admin-operator@example.com",
        is_staff=True,
    )
    request = RequestFactory().post("/admin/rules/rule/")
    request.user = user
    request.request_id = "req-admin-1"
    return request


@pytest.fixture
def rules(db):
    device_type = DeviceType.objects.create(name="temp", metric_unit="C")
    device = Device.objects.create(
        name="Device-1",
        serial_number="SN-0001",
        device_type=device_type,
    )

    rule_a = Rule.objects.create(
        device=device,
        name="Rule A",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=False,
    )
    rule_b = Rule.objects.create(
        device=device,
        name="Rule B",
        condition={"type": "leaf", "operator": "gt", "threshold": 20.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=False,
    )
    rule_c = Rule.objects.create(
        device=device,
        name="Rule C",
        condition={"type": "leaf", "operator": "gt", "threshold": 30.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )
    return rule_a, rule_b, rule_c


@pytest.mark.django_db(transaction=True)
def test_admin_enable_disable_actions_create_explicit_audit_rows(admin_request, rules):
    rule_a, rule_b, rule_c = rules
    queryset = Rule.objects.filter(id__in=[rule_a.id, rule_b.id, rule_c.id])
    RuleAuditLog.objects.all().delete()

    enable_rules(_DummyModelAdmin(), admin_request, queryset)

    enable_logs = RuleAuditLog.objects.filter(action=RuleAuditLog.Action.ENABLE)
    assert enable_logs.count() == 2
    assert {str(log.rule_id) for log in enable_logs} == {str(rule_a.id), str(rule_b.id)}
    for log in enable_logs:
        assert log.changed_fields == ["is_enabled"]
        assert log.before == {"is_enabled": False}
        assert log.after == {"is_enabled": True}
        assert log.source == RuleAuditLog.Source.ADMIN_ACTION
        assert log.actor_username == "admin-operator"
        assert log.request_id == "req-admin-1"

    RuleAuditLog.objects.all().delete()
    disable_queryset = Rule.objects.filter(id__in=[rule_a.id, rule_b.id])
    disable_rules(_DummyModelAdmin(), admin_request, disable_queryset)

    disable_logs = RuleAuditLog.objects.filter(action=RuleAuditLog.Action.DISABLE)
    assert disable_logs.count() == 2
    for log in disable_logs:
        assert log.changed_fields == ["is_enabled"]
        assert log.before == {"is_enabled": True}
        assert log.after == {"is_enabled": False}
        assert log.source == RuleAuditLog.Source.ADMIN_ACTION
