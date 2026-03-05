from __future__ import annotations

from copy import deepcopy

from apps.rules.audit.service import (
    TRACKED_RULE_FIELDS,
    diff_rule_states,
    serialize_rule_state,
    to_json_primitive,
)


def _empty_state() -> dict:
    return {field: None for field in TRACKED_RULE_FIELDS}


def test_sensitive_values_are_redacted():
    data = {
        "token": "abc123",
        "password": "s3cr3t",
        "apikey": "key-inline",
        "Authorization": "Bearer abc",
        "normal": "value",
        "nested": {"api_key": "key-1", "child": "ok"},
    }

    result = to_json_primitive(data)

    assert result["token"] == "***redacted***"
    assert result["password"] == "***redacted***"
    assert result["apikey"] == "***redacted***"
    assert result["Authorization"] == "***redacted***"
    assert result["normal"] == "value"
    assert result["nested"]["api_key"] == "***redacted***"
    assert result["nested"]["child"] == "ok"


def test_serialize_rule_state_returns_tracked_fields_only():
    payload = {
        "name": "Rule A",
        "description": "desc",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 10},
        "action_config": [{"type": "notification", "template_id": 1}],
        "is_enabled": True,
        "device_id": "device-1",
        "extra_field": "must-not-be-included",
    }

    serialized = serialize_rule_state(payload)

    assert set(serialized.keys()) == set(TRACKED_RULE_FIELDS)
    assert "extra_field" not in serialized


def test_diff_rule_states_treats_equivalent_numeric_values_as_unchanged():
    before = _empty_state()
    after = deepcopy(before)

    before["condition"] = {"type": "leaf", "threshold": 10}
    after["condition"] = {"type": "leaf", "threshold": 10.0}

    changed_fields, before_delta, after_delta = diff_rule_states(before, after)

    assert changed_fields == []
    assert before_delta == {}
    assert after_delta == {}


def test_diff_rule_states_detects_list_order_change():
    before = _empty_state()
    after = deepcopy(before)

    before["action_config"] = [
        {"type": "notification", "template_id": 1},
        {"type": "stop_machine", "machine_id": "M-1"},
    ]
    after["action_config"] = list(reversed(before["action_config"]))

    changed_fields, before_delta, after_delta = diff_rule_states(before, after)

    assert changed_fields == ["action_config"]
    assert before_delta["action_config"] == before["action_config"]
    assert after_delta["action_config"] == after["action_config"]
