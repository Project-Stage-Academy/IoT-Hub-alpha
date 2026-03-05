from uuid import uuid4

import pytest

from apps.rules.models import RuleAuditLog


@pytest.mark.django_db
def test_rule_audit_log_creation():
    log = RuleAuditLog.objects.create(
        rule_id=uuid4(),
        action=RuleAuditLog.Action.CREATE,
        changed_fields=["name"],
        before={},
        after={"name": "Rule-1"},
        actor_user_id=11,
        actor_username="operator",
        request_id="req-1",
        source=RuleAuditLog.Source.SIGNAL,
    )

    assert log.id is not None
    assert log.created_at is not None
    assert log.action == RuleAuditLog.Action.CREATE


def test_rule_audit_log_indexes_declared():
    index_names = {index.name for index in RuleAuditLog._meta.indexes}
    assert "idx_r_audit_created_at" in index_names
    assert "idx_r_audit_rule_id" in index_names
    assert "idx_r_audit_action_created" in index_names


def test_rule_audit_log_enum_values():
    action_values = {value for value, _ in RuleAuditLog.Action.choices}
    assert action_values == {"create", "update", "delete", "enable", "disable"}

    source_values = {value for value, _ in RuleAuditLog.Source.choices}
    assert source_values == {"signal", "admin_action", "api", "system"}
