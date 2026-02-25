import types
import pytest
from unittest.mock import PropertyMock


class DummyAtomic:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture()
def fake_settings():
    return types.SimpleNamespace(DB_WRITER_BATCH_SIZE=500)


def set_task_request(monkeypatch, task, retries: int):
    """
    Celery Task.request is usually a read-only property, so patch it as a property.
    """
    monkeypatch.setattr(
        type(task),
        "request",
        PropertyMock(return_value=types.SimpleNamespace(retries=retries)),
        raising=False,
    )


def _patch_devices(tasks_mod, mapping_serial_to_id: dict[str, int]):
    class Dev:
        def __init__(self, id):
            self.id = id

    class DeviceMgr:
        def in_bulk(self, serials, field_name=None):
            return {
                s: Dev(mapping_serial_to_id[s])
                for s in serials
                if s in mapping_serial_to_id
            }

    tasks_mod.Device = types.SimpleNamespace(objects=DeviceMgr())


def _patch_telemetry(tasks_mod, *, bulk_create_raises=None):
    created = {"count": 0}

    class TelemetryMgr:
        def bulk_create(self, objs, batch_size=None):
            if bulk_create_raises is not None:
                raise bulk_create_raises
            created["count"] += len(objs)

    class TelemetryModel:
        objects = TelemetryMgr()

        def __init__(self, payload, device_id):
            self.payload = payload
            self.device_id = device_id

    tasks_mod.Telemetry = TelemetryModel
    return created


def test_bulk_telemetry_write_happy_path(monkeypatch, fake_settings):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {"A": 1, "B": 2})
    created = _patch_telemetry(tasks)

    dlq_calls = {"n": 0}
    monkeypatch.setattr(
        tasks,
        "publish_flush_to_dlq",
        lambda *a, **k: dlq_calls.__setitem__("n", dlq_calls["n"] + 1) or True,
    )

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=0)

    flush = [
        {"device_serial": "A", "payload": {"x": 1}},
        {"device_serial": "B", "payload": {"x": 2}},
    ]

    res = tasks.bulk_telemetry_write.run(flush)

    assert res == {"success": True, "written_to_db": 2, "written_to_dlq": 0}
    assert created["count"] == 2
    assert dlq_calls["n"] == 0


def test_bulk_telemetry_write_some_bad_serials_go_to_dlq(monkeypatch, fake_settings):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {"A": 1})
    created = _patch_telemetry(tasks)

    seen = {"bad": None, "reason": None}
    monkeypatch.setattr(
        tasks,
        "publish_flush_to_dlq",
        lambda _p, bad, reason: seen.update({"bad": bad, "reason": reason}) or True,
    )

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=0)

    flush = [
        {"device_serial": "A", "payload": {"x": 1}},
        {"device_serial": "MISSING", "payload": {"x": 2}},
    ]

    res = tasks.bulk_telemetry_write.run(flush)

    assert res["success"] is True
    assert res["written_to_db"] == 1
    assert res["written_to_dlq"] == 1
    assert created["count"] == 1
    assert seen["reason"] == "Wrong device serial"
    assert seen["bad"] == [{"device_serial": "MISSING", "payload": {"x": 2}}]


def test_bulk_telemetry_write_all_bad_returns_early(monkeypatch, fake_settings):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {})  # no devices
    created = _patch_telemetry(tasks)

    dlq_calls = {"n": 0}
    monkeypatch.setattr(
        tasks,
        "publish_flush_to_dlq",
        lambda *a, **k: dlq_calls.__setitem__("n", dlq_calls["n"] + 1) or True,
    )

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=0)

    flush = [
        {"device_serial": "X", "payload": {"x": 1}},
        {"device_serial": "Y", "payload": {"x": 2}},
    ]

    res = tasks.bulk_telemetry_write.run(flush)

    assert res["written_to_db"] == 0
    assert res["written_to_dlq"] == 2
    assert created["count"] == 0
    assert dlq_calls["n"] == 1


def test_bulk_telemetry_write_db_error_triggers_retry(monkeypatch, fake_settings):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {"A": 1})
    _patch_telemetry(tasks, bulk_create_raises=tasks.OperationalError("db down"))
    monkeypatch.setattr(tasks, "publish_flush_to_dlq", lambda *a, **k: True)

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=1)

    def fake_retry(exc=None, countdown=None):
        raise RuntimeError(f"RETRY_CALLED countdown={countdown}")

    monkeypatch.setattr(tasks.bulk_telemetry_write, "retry", fake_retry)

    with pytest.raises(RuntimeError, match=r"RETRY_CALLED countdown=1"):
        tasks.bulk_telemetry_write.run([{"device_serial": "A", "payload": {"x": 1}}])


def test_bulk_telemetry_write_max_retries_dlq_success(monkeypatch, fake_settings):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {"A": 1})
    _patch_telemetry(tasks, bulk_create_raises=tasks.OperationalError("db down"))
    monkeypatch.setattr(tasks, "publish_flush_to_dlq", lambda *a, **k: True)

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=3)

    monkeypatch.setattr(
        tasks.bulk_telemetry_write,
        "retry",
        lambda **k: (_ for _ in ()).throw(tasks.MaxRetriesExceededError()),
    )

    res = tasks.bulk_telemetry_write.run([{"device_serial": "A", "payload": {"x": 1}}])

    assert res["success"] is True
    assert res["written_to_db"] == 0
    assert res["written_to_dlq"] == 1


def test_bulk_telemetry_write_max_retries_dlq_fail_sets_success_false(
    monkeypatch, fake_settings
):
    import apps.telemetry.tasks as tasks

    monkeypatch.setattr(tasks, "settings", fake_settings)
    monkeypatch.setattr(tasks.transaction, "atomic", lambda: DummyAtomic())
    monkeypatch.setattr(tasks, "get_producer", lambda: object())

    _patch_devices(tasks, {"A": 1})
    _patch_telemetry(tasks, bulk_create_raises=tasks.OperationalError("db down"))
    monkeypatch.setattr(tasks, "publish_flush_to_dlq", lambda *a, **k: False)

    set_task_request(monkeypatch, tasks.bulk_telemetry_write, retries=3)

    monkeypatch.setattr(
        tasks.bulk_telemetry_write,
        "retry",
        lambda **k: (_ for _ in ()).throw(tasks.MaxRetriesExceededError()),
    )

    res = tasks.bulk_telemetry_write.run([{"device_serial": "A", "payload": {"x": 1}}])

    assert res["success"] is False
    assert res["written_to_db"] == 0
    assert res["written_to_dlq"] == 0
