import json
import uuid

import pytest
from django.test import RequestFactory

from apps.devices.models import Device, DeviceType
from apps.rules.models import Rule
from apps.rules.views import RuleListView, RuleDetailView


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def device(db):
    dt = DeviceType.objects.create(name="type-crud", metric_unit="C")
    return Device.objects.create(
        name="Device-CRUD", serial_number="crud-001", device_type=dt
    )


@pytest.fixture
def rule(device):
    return Rule.objects.create(
        name="Test Rule",
        description="A test rule",
        device=device,
        is_enabled=True,
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
    )


def _post_json(rf, path, data):
    return rf.post(path, data=json.dumps(data), content_type="application/json")


def _patch_json(rf, path, data):
    return rf.patch(path, data=json.dumps(data), content_type="application/json")


# ── LIST ────────────────────────────────────────────────────────────────


class TestRuleListGET:
    def test_empty_list(self, rf, db):
        req = rf.get("/api/v1/rules/")
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"] == []
        assert body["pagination"]["total"] == 0

    def test_returns_rules(self, rf, rule):
        req = rf.get("/api/v1/rules/")
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "Test Rule"

    def test_filter_by_device_id(self, rf, rule, device):
        req = rf.get(f"/api/v1/rules/?device_id={device.id}")
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert len(body["data"]) == 1

    def test_filter_by_device_id_no_match(self, rf, rule):
        fake_id = uuid.uuid4()
        req = rf.get(f"/api/v1/rules/?device_id={fake_id}")
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert len(body["data"]) == 0

    def test_filter_by_is_enabled(self, rf, rule):
        req = rf.get("/api/v1/rules/?is_enabled=true")
        resp = RuleListView.as_view()(req)
        body = json.loads(resp.content)
        assert len(body["data"]) == 1

        req = rf.get("/api/v1/rules/?is_enabled=false")
        resp = RuleListView.as_view()(req)
        body = json.loads(resp.content)
        assert len(body["data"]) == 0

    def test_pagination(self, rf, device):
        for i in range(3):
            Rule.objects.create(
                name=f"Rule {i}",
                device=device,
                condition={"type": "leaf", "operator": "gt", "threshold": i},
                action_config=[{"type": "notification", "template_id": 1}],
            )
        req = rf.get("/api/v1/rules/?page=1&page_size=2")
        resp = RuleListView.as_view()(req)
        body = json.loads(resp.content)
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 3
        assert body["pagination"]["next_page"] == 2


# ── CREATE ──────────────────────────────────────────────────────────────


class TestRuleCreatePOST:
    def test_create_success(self, rf, device):
        data = {
            "name": "New Rule",
            "description": "desc",
            "device_id": str(device.id),
            "condition": {"type": "leaf", "operator": "gt", "threshold": 5.0},
            "action_config": [{"type": "notification", "template_id": 2}],
            "is_enabled": True,
        }
        req = _post_json(rf, "/api/v1/rules/", data)
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert body["data"]["name"] == "New Rule"
        assert body["data"]["device_id"] == str(device.id)

    def test_create_missing_required_fields(self, rf, db):
        req = _post_json(rf, "/api/v1/rules/", {"description": "only desc"})
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "name" in body["errors"]
        assert "condition" in body["errors"]
        assert "device_id" in body["errors"]

    def test_create_invalid_condition(self, rf, device):
        data = {
            "name": "Bad Cond",
            "device_id": str(device.id),
            "condition": {"type": "leaf"},
            "action_config": [{"type": "notification", "template_id": 1}],
        }
        req = _post_json(rf, "/api/v1/rules/", data)
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "condition" in body["errors"]

    def test_create_invalid_action_config(self, rf, device):
        data = {
            "name": "Bad Action",
            "device_id": str(device.id),
            "condition": {"type": "leaf", "operator": "gt", "threshold": 5.0},
            "action_config": "not-a-list",
        }
        req = _post_json(rf, "/api/v1/rules/", data)
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "action_config" in body["errors"]

    def test_create_invalid_device_id(self, rf, db):
        data = {
            "name": "Orphan Rule",
            "device_id": str(uuid.uuid4()),
            "condition": {"type": "leaf", "operator": "gt", "threshold": 5.0},
            "action_config": [{"type": "notification", "template_id": 1}],
        }
        req = _post_json(rf, "/api/v1/rules/", data)
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "device_id" in body["errors"]

    def test_create_invalid_json_body(self, rf, db):
        req = rf.post(
            "/api/v1/rules/", data=b"not-json", content_type="application/json"
        )
        resp = RuleListView.as_view()(req)
        assert resp.status_code == 400


# ── DETAIL GET ──────────────────────────────────────────────────────────


class TestRuleDetailGET:
    def test_get_existing(self, rf, rule):
        req = rf.get(f"/api/v1/rules/{rule.pk}/")
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"]["id"] == str(rule.pk)
        assert body["data"]["name"] == "Test Rule"

    def test_get_not_found(self, rf, db):
        fake_id = uuid.uuid4()
        req = rf.get(f"/api/v1/rules/{fake_id}/")
        resp = RuleDetailView.as_view()(req, rule_id=fake_id)
        assert resp.status_code == 404


# ── PATCH ───────────────────────────────────────────────────────────────


class TestRulePATCH:
    def test_patch_name(self, rf, rule):
        req = _patch_json(rf, f"/api/v1/rules/{rule.pk}/", {"name": "Updated"})
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"]["name"] == "Updated"

    def test_patch_is_enabled(self, rf, rule):
        req = _patch_json(rf, f"/api/v1/rules/{rule.pk}/", {"is_enabled": False})
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"]["is_enabled"] is False

    def test_patch_condition(self, rf, rule):
        new_cond = {"type": "leaf", "operator": "lt", "threshold": 99.0}
        req = _patch_json(rf, f"/api/v1/rules/{rule.pk}/", {"condition": new_cond})
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["data"]["condition"]["operator"] == "lt"

    def test_patch_not_found(self, rf, db):
        fake_id = uuid.uuid4()
        req = _patch_json(rf, f"/api/v1/rules/{fake_id}/", {"name": "X"})
        resp = RuleDetailView.as_view()(req, rule_id=fake_id)
        assert resp.status_code == 404

    def test_patch_invalid_condition(self, rf, rule):
        req = _patch_json(
            rf, f"/api/v1/rules/{rule.pk}/", {"condition": {"type": "leaf"}}
        )
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 400


# ── DELETE ──────────────────────────────────────────────────────────────


class TestRuleDELETE:
    def test_delete_existing(self, rf, rule):
        req = rf.delete(f"/api/v1/rules/{rule.pk}/")
        resp = RuleDetailView.as_view()(req, rule_id=rule.pk)
        assert resp.status_code == 204
        assert not Rule.objects.filter(pk=rule.pk).exists()

    def test_delete_not_found(self, rf, db):
        fake_id = uuid.uuid4()
        req = rf.delete(f"/api/v1/rules/{fake_id}/")
        resp = RuleDetailView.as_view()(req, rule_id=fake_id)
        assert resp.status_code == 404
