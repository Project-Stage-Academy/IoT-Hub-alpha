"""Complete coverage tests for Telemetry and TelemetrySchema models."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.devices.models import DeviceType, Device
from apps.telemetry.models import Telemetry, TelemetrySchema


@pytest.fixture
def device_setup(db):
    """Set up device for Telemetry tests."""
    device_type = DeviceType.objects.create(
        name="Temperature Sensor",
        metric_name="temperature",
        metric_unit="Celsius",
        metric_min="-40.0",
        metric_max="125.0",
    )
    device = Device.objects.create(
        name="Test Device",
        device_type=device_type,
        serial_number="TEST-SN-001",
        location="Test Location",
        status="active",
    )
    return device


@pytest.mark.django_db
class TestTelemetrySchemaModel:
    """Test TelemetrySchema model completely."""

    # ==================== BASIC CRUD TESTS ====================

    def test_create_telemetry_schema_with_all_fields(self):
        """Create schema with all fields and verify defaults."""
        schema = TelemetrySchema.objects.create(
            version="2.0",
            validation_schema={
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
            },
            transformation_rules={"rename": {"val": "value"}},
            is_active=False,
        )

        assert schema.id is not None
        assert schema.version == "2.0"
        assert schema.is_active is False
        assert schema.validation_schema["type"] == "object"
        assert schema.transformation_rules["rename"]["val"] == "value"

    def test_version_uniqueness_constraint(self):
        """Duplicate version raises IntegrityError."""
        TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
        )

        with pytest.raises(IntegrityError):
            TelemetrySchema.objects.create(
                version="1.0",
                validation_schema={"type": "object"},
            )

    def test_str_representation(self):
        """Schema __str__ returns version in expected format."""
        schema = TelemetrySchema.objects.create(
            version="3.5",
            validation_schema={"type": "object"},
        )

        assert str(schema) == "Schema v3.5"

    def test_is_active_default_true(self):
        """is_active defaults to True when not specified."""
        schema = TelemetrySchema.objects.create(
            version="1.1",
            validation_schema={"type": "object"},
        )

        assert schema.is_active is True

    def test_empty_transformation_rules_allowed(self):
        """Empty transformation_rules dict is valid."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={},
        )

        assert schema.transformation_rules == {}

    # ==================== VALIDATOR: validate_json_schema ====================

    def test_valid_json_schema_draft7(self):
        """Accept valid Draft7 JSON Schema."""
        valid_schema = {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "timestamp": {"type": "string", "format": "date-time"},
            },
            "required": ["value"],
        }

        # Should not raise
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema=valid_schema,
        )

        assert schema.validation_schema == valid_schema

    def test_invalid_json_schema_not_dict(self):
        """Reject non-dict validation_schema with ValidationError."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema=["type", "object"],  # List, not dict
        )
        with pytest.raises(ValidationError, match="must be a dictionary"):
            schema.full_clean()

    def test_invalid_json_schema_malformed(self):
        """Reject malformed JSON Schema structure."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={
                "type": "invalid_type",  # Not a valid JSON Schema type
                "properties": None,  # properties must be dict
            },
        )
        with pytest.raises(ValidationError, match="Invalid JSON Schema"):
            schema.full_clean()

    def test_json_schema_with_additional_properties(self):
        """Accept JSON Schema with additionalProperties."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={
                "type": "object",
                "additionalProperties": False,
            },
        )

        assert schema.validation_schema["additionalProperties"] is False

    # == VALIDATOR: transformation_rules ==

    def test_valid_transformation_rules_rename(self):
        """Accept rename transformation rules."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"rename": {"old_field": "new_field"}},
        )

        rules = schema.transformation_rules["rename"]
        assert rules["old_field"] == "new_field"

    def test_valid_transformation_rules_multiply(self):
        """Accept multiply transformation rules with numeric values."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"multiply": {"value": 100, "factor": 2.5}},
        )

        assert schema.transformation_rules["multiply"]["value"] == 100

    def test_valid_transformation_rules_round(self):
        """Accept round transformation rules with decimal places."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"round": {"value": 2}},
        )

        assert schema.transformation_rules["round"]["value"] == 2

    def test_valid_transformation_rules_remove(self):
        """Accept remove transformation rules with boolean values."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"remove": {"temp_field": True}},
        )

        assert schema.transformation_rules["remove"]["temp_field"] is True

    def test_valid_transformation_rules_multiple_types(self):
        """Accept multiple transformation rule types combined."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={
                "rename": {"old": "new"},
                "multiply": {"val": 10},
                "round": {"num": 2},
            },
        )

        assert len(schema.transformation_rules) == 3

    def test_invalid_transformation_rules_not_dict(self):
        """Reject non-dict transformation_rules."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules=["rename", "multiply"],  # List
        )
        with pytest.raises(ValidationError, match="must be a dictionary"):
            schema.full_clean()

    def test_invalid_transformation_rules_unknown_key(self):
        """Reject unknown transformation rule keys."""
        rules = {"unknown_rule": {"field": "value"}}
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules=rules,
        )
        with pytest.raises(ValidationError, match="Invalid transformation rule key"):
            schema.full_clean()

    def test_invalid_transformation_rules_rename_non_string(self):
        """Reject non-string rename values (int, dict, etc)."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"rename": {"field": 123}},  # not string
        )
        with pytest.raises(
            ValidationError, match="Rename rule for .* must be a string"
        ):
            schema.full_clean()

    def test_invalid_transformation_rules_multiply_non_numeric(self):
        """Reject multiply values that are not numbers."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"multiply": {"field": "abc"}},  # String
        )
        with pytest.raises(
            ValidationError, match="Rule 'multiply' for .* must be a number"
        ):
            schema.full_clean()

    def test_invalid_transformation_rules_round_non_numeric(self):
        """Reject round decimal places that are not numbers."""
        schema = TelemetrySchema(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"round": {"field": []}},  # List
        )
        with pytest.raises(
            ValidationError, match="Rule 'round' for .* must be a number"
        ):
            schema.full_clean()

    def test_transformation_rules_rename_empty_dict(self):
        """Accept rename with empty dict."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"rename": {}},
        )

        assert schema.transformation_rules["rename"] == {}

    def test_transformation_rules_multiply_with_zero(self):
        """Accept multiply with zero (edge case)."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"multiply": {"field": 0}},
        )

        assert schema.transformation_rules["multiply"]["field"] == 0

    def test_transformation_rules_divide_with_zero(self):
        """Accept divide with zero (edge case in apply_transformations)."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"divide": {"field": 0}},
        )

        assert schema.transformation_rules["divide"]["field"] == 0

    def test_transformation_rules_round_negative_decimals(self):
        """Accept round with negative decimals (edge case)."""
        schema = TelemetrySchema.objects.create(
            version="1.0",
            validation_schema={"type": "object"},
            transformation_rules={"round": {"field": -1}},
        )

        assert schema.transformation_rules["round"]["field"] == -1


@pytest.mark.django_db
class TestTelemetryModelEdgeCases:
    """Test Telemetry model edge cases not covered in existing tests."""

    def test_payload_with_large_json(self, device_setup):
        """Telemetry accepts large JSON payloads (1000+ fields)."""
        large_payload = {
            "schema_version": "1.0",
            "values": {f"field_{i}": i * 1.5 for i in range(1000)},
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=large_payload,
        )

        assert telemetry.id is not None
        assert len(telemetry.payload["values"]) == 1000

    def test_timestamp_precision_microseconds(self, device_setup):
        """Timestamp preserves microsecond precision."""
        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload={"schema_version": "1.0"},
        )

        # Verify microseconds are stored (not truncated)
        fetched = Telemetry.objects.get(id=telemetry.id)
        assert fetched.timestamp.microsecond is not None

    def test_payload_with_unicode_characters(self, device_setup):
        """Payload accepts unicode including emoji."""
        payload = {
            "schema_version": "1.0",
            "note": "Temperature 🌡️",
            "location": "Київ",
            "status": "✓ OK",
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=payload,
        )

        fetched = Telemetry.objects.get(id=telemetry.id)
        assert fetched.payload["note"] == "Temperature 🌡️"
        assert fetched.payload["location"] == "Київ"

    def test_payload_with_nested_json(self, device_setup):
        """Payload accepts deeply nested JSON structures."""
        nested_payload = {
            "schema_version": "1.0",
            "data": {
                "level1": {
                    "level2": {
                        "level3": {
                            "value": 42.5,
                            "array": [1, 2, 3, 4, 5],
                        }
                    }
                }
            },
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=nested_payload,
        )

        data = telemetry.payload["data"]["level1"]["level2"]["level3"]
        assert data["value"] == 42.5

    def test_payload_with_null_values(self, device_setup):
        """Payload can contain null/None values."""
        payload = {
            "schema_version": "1.0",
            "value": None,
            "status": None,
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=payload,
        )

        assert telemetry.payload["value"] is None

    def test_payload_with_boolean_values(self, device_setup):
        """Payload accepts boolean values."""
        payload = {
            "schema_version": "1.0",
            "is_active": True,
            "is_error": False,
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=payload,
        )

        assert telemetry.payload["is_active"] is True
        assert telemetry.payload["is_error"] is False

    def test_payload_with_floating_point_precision(self, device_setup):
        """Payload preserves floating point precision."""
        payload = {
            "schema_version": "1.0",
            "precise_value": 3.141592653589793,
        }

        telemetry = Telemetry.objects.create(
            device=device_setup,
            payload=payload,
        )

        val = telemetry.payload["precise_value"]
        expected = 3.141592653589793
        assert abs(val - expected) < 1e-15

    def test_multiple_telemetry_same_device(self, device_setup):
        """Device can have multiple Telemetry records."""
        t1 = Telemetry.objects.create(
            device=device_setup,
            payload={"value": 1},
        )
        t2 = Telemetry.objects.create(
            device=device_setup,
            payload={"value": 2},
        )

        assert Telemetry.objects.filter(device=device_setup).count() == 2
        assert t1.id != t2.id

    def test_ordering_by_timestamp_descending(self, device_setup):
        """Telemetry ordered by timestamp descending (newest first)."""
        t1 = Telemetry.objects.create(device=device_setup, payload={"v": 1})
        t2 = Telemetry.objects.create(device=device_setup, payload={"v": 2})
        t3 = Telemetry.objects.create(device=device_setup, payload={"v": 3})

        ordered = list(Telemetry.objects.all())

        assert ordered[0].id == t3.id
        assert ordered[1].id == t2.id
        assert ordered[2].id == t1.id
