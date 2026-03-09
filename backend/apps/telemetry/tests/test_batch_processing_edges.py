"""Tests for batch processing edge cases and validation."""

import pytest

from apps.telemetry.producers import (
    _assert_batch_serial_matches,
    _assert_event_serial_matches,
)


class TestBatchSerialMatching:
    """Test batch serial number validation edge cases."""

    def test_empty_serial_in_batch_event_raises(self):
        """Empty string serial number in batch event raises ValueError."""
        batch = [{"serial_number": "", "value": 42}]

        with pytest.raises(ValueError, match="non-empty serial_number"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_null_serial_in_batch_event_raises(self):
        """None serial number in batch event raises ValueError."""
        batch = [{"serial_number": None, "value": 42}]

        with pytest.raises(ValueError, match="non-empty serial_number"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_whitespace_only_serial_raises(self):
        """Whitespace-only serial number raises ValueError."""
        batch = [{"serial_number": "   ", "value": 42}]

        with pytest.raises(ValueError, match="non-empty serial_number"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_mismatched_serial_in_batch_raises(self):
        """Mismatched serial number in batch event raises ValueError."""
        batch = [{"serial_number": "SN-002", "value": 42}]

        with pytest.raises(ValueError, match="serial_number mismatch"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_first_event_invalid_stops_batch(self):
        """First invalid event in batch stops processing."""
        batch = [
            {"serial_number": "", "value": 1},  # Invalid
            {"serial_number": "SN-001", "value": 2},  # Would be valid
        ]

        with pytest.raises(ValueError):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_empty_batch_raises(self):
        """Empty batch raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            _assert_batch_serial_matches([], "SN-001")

    def test_valid_single_event_batch(self):
        """Valid single-event batch passes validation."""
        batch = [{"serial_number": "SN-001", "value": 42}]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-001")

    def test_valid_multiple_event_batch(self):
        """Valid multiple-event batch passes validation."""
        batch = [
            {"serial_number": "SN-001", "value": 1},
            {"serial_number": "SN-001", "value": 2},
            {"serial_number": "SN-001", "value": 3},
        ]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-001")

    def test_valid_large_batch_1000_events(self):
        """Large batch with 1000 events validates successfully."""
        batch = [{"serial_number": "SN-001", "value": i} for i in range(1000)]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-001")

    def test_valid_very_large_batch_10000_events(self):
        """Very large batch with 10000 events validates (performance test)."""
        batch = [{"serial_number": "SN-001", "value": i} for i in range(10000)]

        # Should complete without timeout
        _assert_batch_serial_matches(batch, "SN-001")

    def test_batch_with_unicode_serial(self):
        """Batch with unicode serial numbers validates."""
        batch = [{"serial_number": "SN-температура", "value": 42}]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-температура")

    def test_batch_event_with_extra_fields(self):
        """Batch events with extra fields validate (only serial checked)."""
        batch = [
            {
                "serial_number": "SN-001",
                "value": 42,
                "extra_field": "ignored",
                "another": 123,
            }
        ]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-001")

    def test_single_event_validation(self):
        """Single event serial validation works."""
        event = {"serial_number": "SN-001", "value": 42}

        # Should not raise
        _assert_event_serial_matches(event, "SN-001")

    def test_single_event_mismatch(self):
        """Single event with mismatched serial raises."""
        event = {"serial_number": "SN-002", "value": 42}

        with pytest.raises(ValueError, match="serial_number mismatch"):
            _assert_event_serial_matches(event, "SN-001")

    def test_single_event_empty_serial(self):
        """Single event with empty serial raises."""
        event = {"serial_number": "", "value": 42}

        with pytest.raises(ValueError, match="non-empty serial_number"):
            _assert_event_serial_matches(event, "SN-001")

    def test_batch_second_event_invalid(self):
        """Invalid event in middle of batch caught."""
        batch = [
            {"serial_number": "SN-001", "value": 1},  # Valid
            {"serial_number": "SN-002", "value": 2},  # Invalid (mismatch)
            {"serial_number": "SN-001", "value": 3},  # Would be valid
        ]

        with pytest.raises(ValueError, match="serial_number mismatch"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_batch_last_event_invalid(self):
        """Invalid event at end of batch caught."""
        batch = [
            {"serial_number": "SN-001", "value": 1},
            {"serial_number": "SN-001", "value": 2},
            {"serial_number": "", "value": 3},  # Invalid at end
        ]

        with pytest.raises(ValueError, match="non-empty serial_number"):
            _assert_batch_serial_matches(batch, "SN-001")

    def test_error_message_includes_context(self):
        """Error message includes helpful context."""
        batch = [{"serial_number": "WRONG", "value": 42}]

        with pytest.raises(ValueError) as exc_info:
            _assert_batch_serial_matches(batch, "EXPECTED")

        error_msg = str(exc_info.value)
        # Should include both serial numbers for debugging
        assert "WRONG" in error_msg or "mismatch" in error_msg

    def test_batch_with_mixed_field_types(self):
        """Batch events with various data types validate."""
        batch = [
            {"serial_number": "SN-001", "value": 42},
            {"serial_number": "SN-001", "value": 3.14},
            {"serial_number": "SN-001", "value": "string"},
            {"serial_number": "SN-001", "value": [1, 2, 3]},
            {"serial_number": "SN-001", "value": {"nested": "dict"}},
        ]

        # Should not raise - validation only checks serial_number
        _assert_batch_serial_matches(batch, "SN-001")

    def test_batch_with_null_values(self):
        """Batch events with null values validate."""
        batch = [
            {"serial_number": "SN-001", "value": None},
            {"serial_number": "SN-001", "value": None},
        ]

        # Should not raise
        _assert_batch_serial_matches(batch, "SN-001")

    def test_special_characters_in_serial(self):
        """Special characters in serial numbers validated."""
        special_serials = [
            "SN-001!",
            "SN@001",
            "SN#001",
            "SN-001/002",
        ]

        for serial in special_serials:
            batch = [{"serial_number": serial, "value": 42}]
            # Should validate successfully (no format restrictions)
            _assert_batch_serial_matches(batch, serial)
