from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from apps.rules.models import RuleAuditLog


def _make_user_with_audit_perm() -> object:
    user = get_user_model().objects.create_user(
        username=f"audit-user-{uuid4().hex[:8]}",
        password="pass-123",
        email="audit-user@example.com",
    )
    perm = Permission.objects.get(codename="view_ruleauditlog")
    user.user_permissions.add(perm)
    return user


def _create_audit_log(**overrides) -> RuleAuditLog:
    payload = {
        "rule_id": uuid4(),
        "action": RuleAuditLog.Action.CREATE,
        "changed_fields": ["name"],
        "before": {},
        "after": {"name": "Rule"},
        "actor_user_id": 1,
        "actor_username": "alice",
        "request_id": "req-1",
        "source": RuleAuditLog.Source.SIGNAL,
    }
    payload.update(overrides)
    return RuleAuditLog.objects.create(**payload)


@pytest.mark.django_db
def test_audit_api_permission_checks():
    client = Client()

    response = client.get("/api/v1/rules/audit/")
    assert response.status_code == 401

    user_without_perm = get_user_model().objects.create_user(
        username="no-perm-user",
        password="pass-123",
        email="noperm@example.com",
    )
    client.force_login(user_without_perm)

    response = client.get("/api/v1/rules/audit/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_audit_api_filters_by_rule_action_time_actor_and_request_id():
    old_log = _create_audit_log(
        action=RuleAuditLog.Action.UPDATE,
        actor_username="operator-a",
        request_id="req-old",
    )
    new_log = _create_audit_log(
        action=RuleAuditLog.Action.DELETE,
        actor_username="operator-b",
        request_id="req-new",
    )

    old_ts = timezone.now() - timedelta(days=5)
    RuleAuditLog.objects.filter(id=old_log.id).update(created_at=old_ts)

    user = _make_user_with_audit_perm()
    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/rules/audit/?rule_id={old_log.rule_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == old_log.id

    response = client.get(f"/api/v1/rules/audit/?action={RuleAuditLog.Action.DELETE}")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == new_log.id

    from_ts = (timezone.now() - timedelta(days=2)).isoformat()
    response = client.get("/api/v1/rules/audit/", {"from": from_ts})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == new_log.id

    response = client.get("/api/v1/rules/audit/?actor=operator-a")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == old_log.id

    response = client.get("/api/v1/rules/audit/?request_id=req-new")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["id"] == new_log.id


@pytest.mark.django_db
def test_audit_api_pagination_and_detail():
    _create_audit_log(request_id="req-1")
    second = _create_audit_log(request_id="req-2")
    _create_audit_log(request_id="req-3")

    user = _make_user_with_audit_perm()
    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/rules/audit/?page=2&page_size=2")
    assert response.status_code == 200
    body = response.json()

    pagination = body["pagination"]
    assert pagination["page"] == 2
    assert pagination["page_size"] == 2
    assert pagination["total"] == 3
    assert pagination["total_pages"] == 2
    assert pagination["next_page"] is None
    assert pagination["prev_page"] == 1
    assert len(body["data"]) == 1

    response = client.get(f"/api/v1/rules/audit/{second.id}/")
    assert response.status_code == 200
    detail = response.json()["data"]
    assert detail["id"] == second.id

    response = client.get("/api/v1/rules/audit/999999/")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "expected_error"),
    [
        ("page=abc", "page must be an integer"),
        ("page_size=999999", "page_size must be <= 1000"),
        ("rule_id=not-a-uuid", "rule_id must be a valid UUID"),
        ("from=not-a-date", "from must be a valid ISO-8601 datetime"),
        ("to=not-a-date", "to must be a valid ISO-8601 datetime"),
        ("from=2026-01-02T00:00:00Z&to=2026-01-01T00:00:00Z", "from must be <= to"),
        ("action=bad-action", "Invalid action filter value."),
    ],
)
def test_audit_api_invalid_query_params_return_400(query, expected_error):
    user = _make_user_with_audit_perm()
    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/rules/audit/?{query}")

    assert response.status_code == 400
    assert response.json()["error"] == expected_error
