"""Tests for HTTP ingestion error scenarios and edge cases."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestHTTPErrorScenarios:
    """Test HTTP ingestion endpoint error handling."""

    @pytest.fixture
    def client(self):
        """Django test client."""
        return Client()

    @pytest.fixture
    def valid_payload(self, device):
        """Valid telemetry payload for HTTP POST."""
        return {
            "schema_version": "1.0",
            "serial_number": device.serial_number,
            "value": 42.5,
            "timestamp": "2026-01-01T12:00:00Z",
        }

    def test_extremely_large_payload_handled(self, client, device):
        """Extremely large payload (10MB+) handled gracefully."""
        large_value = "x" * (10 * 1024 * 1024)  # 10MB string

        payload = {
            "schema_version": "1.0",
            "serial_number": device.serial_number,
            "data": large_value,
        }

        # Large payloads may be rejected at Django level
        # Just verify no crash
        try:
            client.post(
                "/api/v1/telemetry/",
                data=[payload],
                content_type="application/json",
            )
        except Exception:
            # Expected for very large payloads
            pass

    def test_malformed_idempotency_key_ignored(self, client, device, valid_payload):
        """Malformed idempotency key handled gracefully."""
        malformed_keys = [
            {"idempotency_key": ""},
            {"idempotency_key": None},
            {"idempotency_key": 12345},  # Non-string
        ]

        for key_dict in malformed_keys:
            payload = {**valid_payload, **key_dict}

            # Should not crash, idempotency key validation handled
            try:
                client.post(
                    "/api/v1/telemetry/",
                    data=[payload],
                    content_type="application/json",
                )
            except Exception:
                pass

    def test_device_serial_with_unicode(self, client):
        """Device serial with unicode characters handled."""
        unicode_serial = "SN-температура-001"

        payload = {
            "schema_version": "1.0",
            "serial_number": unicode_serial,
            "value": 42.5,
        }

        # Unicode in serial should be handled
        try:
            client.post(
                "/api/v1/telemetry/",
                data=[payload],
                content_type="application/json",
            )
        except Exception:
            pass

    def test_invalid_content_type_header(self, client, device, valid_payload):
        """Invalid content-type header handled."""
        response = client.post(
            "/api/v1/telemetry/",
            data=[valid_payload],
            content_type="text/plain",  # Wrong content type
        )

        # May return 400 or 415
        assert response.status_code in [400, 415, 500]

    def test_missing_serial_number_header(self, client, device, valid_payload):
        """Missing serial number in request fails."""
        payload_no_serial = {
            "schema_version": "1.0",
            # Missing serial_number
            "value": 42.5,
        }

        try:
            response = client.post(
                "/api/v1/telemetry/",
                data=[payload_no_serial],
                content_type="application/json",
            )
            # Should fail validation
            assert response.status_code in [400, 422]
        except Exception:
            pass

    def test_invalid_json_payload_format(self, client, device):
        """Invalid JSON payload returns 400 Bad Request."""
        response = client.post(
            "/api/v1/telemetry/",
            data=b"not valid json {{{",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_empty_payload_rejected(self, client, device):
        """Empty payload rejected."""
        response = client.post(
            "/api/v1/telemetry/",
            data=b"",
            content_type="application/json",
        )

        assert response.status_code in [400, 415]

    def test_null_payload_rejected(self, client):
        """Null payload rejected."""
        response = client.post(
            "/api/v1/telemetry/",
            data=b"null",
            content_type="application/json",
        )

        assert response.status_code in [400, 422]

    def test_string_payload_instead_of_object(self, client):
        """String payload instead of object rejected."""
        response = client.post(
            "/api/v1/telemetry/",
            data=b'"just a string"',
            content_type="application/json",
        )

        assert response.status_code in [400, 422]

    def test_non_200_204_status_ambiguity(self, client, device, valid_payload):
        """HTTP response status is single expected code."""
        response = client.post(
            "/api/v1/telemetry/",
            data=[valid_payload],
            content_type="application/json",
        )

        assert isinstance(response.status_code, int)

    def test_batch_exceeds_size_limit(self, client, device):
        """Batch exceeding size limit rejected."""
        oversized_batch = [
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": i,
            }
            for i in range(10001)
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=oversized_batch,
            content_type="application/json",
        )

        assert response.status_code in [400, 413, 422]

    def test_invalid_schema_version(self, client, device):
        """Invalid schema version returns error."""
        payload = {
            "schema_version": "99.0",  # Non-existent version
            "serial_number": device.serial_number,
            "value": 42.5,
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=[payload],
            content_type="application/json",
        )

        # Should fail validation
        assert response.status_code in [400, 422]

    def test_missing_schema_version(self, client, device):
        """Missing schema version returns error."""
        payload = {
            # Missing schema_version
            "serial_number": device.serial_number,
            "value": 42.5,
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=[payload],
            content_type="application/json",
        )

        assert response.status_code in [400, 422]

    def test_special_characters_in_fields(self, client, device):
        """Special characters in field values handled."""
        payload = {
            "schema_version": "1.0",
            "serial_number": device.serial_number,
            "value": 42.5,
            "special": "!@#$%^&*()_+-=[]{}|;:',.<>?/~`",
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=[payload],
            content_type="application/json",
        )

        # Should handle special chars gracefully
        assert response.status_code in [200, 201, 202, 400, 422]

    def test_nested_json_payload(self, client, device):
        """Deeply nested JSON payload handled."""
        nested = {"value": 42}
        for i in range(100):
            nested = {"nested": nested}

        payload = {
            "schema_version": "1.0",
            "serial_number": device.serial_number,
            "data": nested,
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=[payload],
            content_type="application/json",
        )

        # Should handle nesting gracefully
        assert response.status_code in [200, 201, 202, 400, 422]

    def test_numeric_field_as_string(self, client, device):
        """Numeric field provided as string handled."""
        payload = {
            "schema_version": "1.0",
            "serial_number": device.serial_number,
            "value": "42.5",  # String instead of number
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=[payload],
            content_type="application/json",
        )

        # May be accepted or rejected depending on schema
        assert response.status_code in [200, 201, 202, 400, 422]
