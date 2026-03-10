from __future__ import annotations

from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.rules.models import RuleAuditLog


def _create_log() -> RuleAuditLog:
    return RuleAuditLog.objects.create(
        rule_id=uuid4(),
        action=RuleAuditLog.Action.CREATE,
        changed_fields=["name"],
        before={},
        after={"name": "Rule"},
        actor_user_id=1,
        actor_username="operator",
        request_id="req-1",
        source=RuleAuditLog.Source.SIGNAL,
    )


@pytest.mark.django_db
def test_purge_rule_audit_dry_run_reports_without_delete():
    old_log = _create_log()
    _create_log()

    RuleAuditLog.objects.filter(id=old_log.id).update(
        created_at=timezone.now() - timedelta(days=200)
    )

    output = StringIO()
    call_command("purge_rule_audit", days=30, dry_run=True, stdout=output)

    assert "would delete 1 rule audit row" in output.getvalue().lower()
    assert RuleAuditLog.objects.count() == 2


@pytest.mark.django_db
def test_purge_rule_audit_deletes_only_older_than_threshold():
    old_log = _create_log()
    new_log = _create_log()

    RuleAuditLog.objects.filter(id=old_log.id).update(
        created_at=timezone.now() - timedelta(days=200)
    )

    output = StringIO()
    call_command("purge_rule_audit", days=30, stdout=output)

    assert "deleted 1 rule audit row" in output.getvalue().lower()
    assert RuleAuditLog.objects.filter(id=old_log.id).exists() is False
    assert RuleAuditLog.objects.filter(id=new_log.id).exists() is True


@pytest.mark.django_db
def test_purge_rule_audit_rejects_non_positive_days():
    with pytest.raises(CommandError, match="days must be >= 1"):
        call_command("purge_rule_audit", days=0)
