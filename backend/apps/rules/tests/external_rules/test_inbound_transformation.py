from __future__ import annotations

import pytest
from datetime import datetime, timezone as dt_timezone

from apps.rules.services.inbound_transform import TransformEngine, TransformationError
from apps.rules.services.data_structure import ExternalEventMessage


@pytest.fixture
def engine():
    return TransformEngine()


def test_cast_value_primitives(engine):
    assert engine._cast_value(123, "str") == "123"
    assert engine._cast_value("123", "int") == 123
    assert engine._cast_value("1.5", "float") == 1.5
    assert engine._cast_value("yes", "bool") is True
    assert engine._cast_value("no", "bool") is False
    assert engine._cast_value(0, "bool") is False
    assert engine._cast_value(1, "bool") is True


def test_convert_time_valid_with_offset(engine):
    out = engine._convert_time("2026-02-24T10:00:00+02:00")
    assert out.startswith("2026-02-24T08:00:00")
    assert out.endswith("+00:00")


def test_convert_time_naive_assumes_utc(engine):
    out = engine._convert_time("2026-02-24T10:00:00")
    assert out.startswith("2026-02-24T10:00:00")
    assert out.endswith("+00:00")


def test_convert_time_invalid_returns_tz_now_iso(monkeypatch, engine):
    import apps.rules.services.inbound_transform as mod

    fixed = datetime(2026, 2, 24, 12, 0, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(mod.tz, "now", lambda: fixed)

    out = engine._convert_time("not-a-date")
    assert out == fixed.isoformat()


def test_handle_literal_allows_only_literal(engine):
    spec = {"literal": ["warning", "critical"]}
    assert engine._handle_literal(spec, "warning", "severity") == "warning"

    with pytest.raises(TransformationError) as e:
        engine._handle_literal(spec, "info", "severity")
    assert "can only accept" in str(e.value)


def test_get_inner_dict_from_existing(engine):
    body = {"payload": {"a": 1}}
    spec = {"from": "payload"}
    inner = engine._get_inner_dict(spec, body, "x")
    assert inner == {"a": 1}


def test_get_inner_dict_default_when_missing(engine):
    body = {}
    spec = {"from": "payload", "default": {"a": 1}}
    inner = engine._get_inner_dict(spec, body, "x")
    assert inner == {"a": 1}


def test_get_inner_dict_raises_when_not_dict(engine):
    body = {"payload": "not-a-dict"}
    spec = {"from": "payload"}
    with pytest.raises(TransformationError) as e:
        engine._get_inner_dict(spec, body, "x")
    assert "inner source must be a dict" in str(e.value)


def test_check_list_raises_if_data_not_list(engine):
    spec = {"from": "items", "list": {"x": {"from": "a"}}}
    with pytest.raises(TransformationError) as e:
        engine._check_list(spec, data_list="abc", target_key="items_out")
    assert "expected list" in str(e.value)


def test_init_transform_simple_from_default_cast(engine):
    mapping = {
        "rule_id": {"from": "rid"},
        "device_id": {"from": "did"},
        "severy": {
            "from": "sev",
            "default": "warning",
            "literal": ["warning", "critical"],
        },
        "cooldown_min": {"default": "60", "cast": "int"},
    }
    body = {"rid": "r1", "did": "d1"}
    out = engine._init_transform(mapping, {}, body)
    assert out["rule_id"] == "r1"
    assert out["device_id"] == "d1"
    assert out["severy"] == "warning"
    assert out["cooldown_min"] == 60


def test_init_transform_inner_dict(engine):
    mapping = {
        "telemetry_snapshot": {
            "from": "telemetry",
            "inner_dict": {
                "temp": {"from": "t", "cast": "float"},
            },
        },
        "rule_id": {"from": "rid"},
        "device_id": {"from": "did"},
    }
    body = {"rid": "r1", "did": "d1", "telemetry": {"t": "22.5"}}
    out = engine._init_transform(mapping, {}, body)
    assert out["telemetry_snapshot"] == {"temp": 22.5}


def test_init_transform_list(engine):
    mapping = {
        "execution_results": {
            "from": "results",
            "list": {
                "ok": {"from": "ok", "cast": "bool"},
                "value": {"from": "v", "cast": "float"},
            },
        },
        "rule_id": {"from": "rid"},
        "device_id": {"from": "did"},
    }
    body = {
        "rid": "r1",
        "did": "d1",
        "results": [{"ok": "yes", "v": "1.2"}, {"ok": "no", "v": "2.5"}],
    }

    engine.body = body
    out = engine._init_transform(mapping, {}, body)

    assert out["execution_results"] == [
        {"ok": True, "value": 1.2},
        {"ok": False, "value": 2.5},
    ]


def test_get_map_or_die_id_not_found_raises(engine, monkeypatch):
    import apps.rules.services.inbound_transform as mod

    def fake_open(*args, **kwargs):
        raise AssertionError("Should not open file in this test")

    monkeypatch.setattr(mod.Path, "open", fake_open, raising=False)
    monkeypatch.setattr(
        engine,
        "_get_map_or_die",
        lambda _id: (_ for _ in ()).throw(TransformationError("x ID not found")),
    )

    with pytest.raises(TransformationError):
        engine.transform(999, {"rid": "r1", "did": "d1"})


def test_transform_validation_error_wrapped(engine, monkeypatch):
    monkeypatch.setattr(engine, "_get_map_or_die", lambda _id: {"x": {"default": 1}})
    with pytest.raises(TransformationError) as e:
        engine.transform(1, {})
    assert "Validation error" in str(e.value)


def test_transform_success(engine, monkeypatch):
    mapping = {
        "rule_id": {"from": "rid"},
        "device_id": {"from": "did"},
    }
    monkeypatch.setattr(engine, "_get_map_or_die", lambda _id: mapping)

    msg = engine.transform(1, {"rid": "r1", "did": "d1"})
    assert isinstance(msg, ExternalEventMessage)
    assert msg.rule_id == "r1"
    assert msg.device_id == "d1"
