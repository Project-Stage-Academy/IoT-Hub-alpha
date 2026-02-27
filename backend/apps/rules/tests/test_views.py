import json
import pytest
from django.test import RequestFactory

from apps.rules.views import ExternalRule
from apps.rules.services.data_structure import ExternalEventMessage
from apps.rules.services.inbound_transform import TransformationError


@pytest.fixture
def rf():
    return RequestFactory()


def test_external_rule_empty_body_returns_400(rf, monkeypatch):
    monkeypatch.setattr("apps.rules.views.get_json_body", lambda b: {})
    req = rf.post("/api/v1/rules/inbound/", data=b"", content_type="application/json")

    resp = ExternalRule.as_view()(req, inbound_id=1)
    assert resp.status_code == 400


def test_external_rule_transform_error_returns_400(rf, monkeypatch):
    monkeypatch.setattr("apps.rules.views.get_json_body", lambda b: {"x": 1})

    def boom(*args, **kwargs):
        raise TransformationError("bad")

    monkeypatch.setattr("apps.rules.views.TransformEngine.transform", boom)

    req = rf.post(
        "/api/v1/rules/inbound/",
        data=json.dumps({"x": 1}),
        content_type="application/json",
    )
    resp = ExternalRule.as_view()(req, inbound_id=1)

    assert resp.status_code == 400
    payload = json.loads(resp.content)
    assert "Failed:" in payload["error"]


def test_external_rule_success_returns_202(rf, monkeypatch):
    monkeypatch.setattr(
        "apps.rules.views.get_json_body", lambda b: {"rid": "r1", "did": "d1"}
    )

    msg = ExternalEventMessage.model_validate({"rule_id": "r1", "device_id": "d1"})

    monkeypatch.setattr(
        "apps.rules.views.TransformEngine.transform", lambda self, inbound_id, body: msg
    )

    req = rf.post(
        "/api/v1/rules/inbound/",
        data=json.dumps({"rid": "r1"}),
        content_type="application/json",
    )
    resp = ExternalRule.as_view()(req, inbound_id=1)

    assert resp.status_code == 202
    payload = json.loads(resp.content)
    assert payload["rule_id"] == "r1"
    assert payload["device_id"] == "d1"
