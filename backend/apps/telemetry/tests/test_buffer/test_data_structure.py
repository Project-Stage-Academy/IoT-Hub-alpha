from dataclasses import is_dataclass


def test_dataclasses_exist_and_shape():
    from apps.telemetry.service_layer.data_structure import BufferedItem, InFlight

    assert is_dataclass(BufferedItem)
    assert is_dataclass(InFlight)

    bi_fields = {f.name for f in BufferedItem.__dataclass_fields__.values()}
    assert {"kafka_msg", "payload", "device_serial"} <= bi_fields

    inflight_fields = {f.name for f in InFlight.__dataclass_fields__.values()}
    assert {"flush", "offsets", "start"} <= inflight_fields
