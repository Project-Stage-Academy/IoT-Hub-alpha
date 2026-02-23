import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _kafka_mode(settings):
    settings.TELEMETRY_PIPELINE_MODE = "kafka"
    settings.TELEMETRY_MAX_BATCH_SIZE = 1000


@pytest.fixture
def mock_producer():
    with patch("apps.telemetry.views.get_producer") as mock_get:
        producer = MagicMock()
        producer.publish_raw.return_value = "telemetry.raw"
        producer.publish_raw_batch.return_value = "telemetry.raw"
        mock_get.return_value = producer
        yield producer


class TestTelemetryIngestViewKafka:
    serial_number = "TEMP-SN-002"

    def test_single_payload_published(self, client, mock_producer):
        payload = {"schema_version": "1.0", "value": 2550}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["count"] == 1
        assert body["topic"] == "telemetry.raw"
        assert body["pipeline_mode"] == "kafka"
        mock_producer.publish_raw.assert_called_once()
        mock_producer.publish_raw_batch.assert_not_called()

        call_kwargs = mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["serial_number"] == self.serial_number
        assert call_kwargs["source"] == "http"
        assert call_kwargs["data"]["serial_number"] == self.serial_number
        assert call_kwargs["data"]["ingest_protocol"] == "http"

    def test_batch_payload_uses_publish_raw_batch(self, client, mock_producer):
        payload = [
            {"schema_version": "1.0", "value": 100},
            {"schema_version": "1.0", "value": 200},
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["count"] == 2
        mock_producer.publish_raw_batch.assert_called_once()
        mock_producer.publish_raw.assert_not_called()

        call_kwargs = mock_producer.publish_raw_batch.call_args.kwargs
        assert call_kwargs["serial_number"] == self.serial_number
        assert call_kwargs["source"] == "http"
        assert len(call_kwargs["data"]) == 2
        for event in call_kwargs["data"]:
            assert event["serial_number"] == self.serial_number
            assert event["ingest_protocol"] == "http"

    def test_idempotency_key_is_trimmed_and_passed(self, client, mock_producer):
        payload = {"schema_version": "1.0", "value": 1}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
            HTTP_IDEMPOTENCY_KEY="  test-key-123  ",
        )

        assert response.status_code == 202
        body = response.json()
        assert body["idempotency_key"] == "test-key-123"
        call_kwargs = mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["data"]["idempotency_key"] == "test-key-123"

    def test_missing_serial_number_header(self, client):
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps({"schema_version": "1.0"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        body = response.json()
        assert "X-Device-Serial-Number header is required" in body["error"]

    def test_invalid_json(self, client):
        response = client.post(
            "/api/v1/telemetry/",
            data="not valid json",
            content_type="application/json",
        )

        assert response.status_code == 400
        body = response.json()
        assert "Invalid JSON payload" in body["error"]

    def test_empty_batch(self, client):
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps([]),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 400
        body = response.json()
        assert "Empty batch" in body["error"]

    def test_batch_exceeds_limit(self, client, settings):
        settings.TELEMETRY_MAX_BATCH_SIZE = 2
        payload = [{"schema_version": "1.0"}] * 3

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 400
        body = response.json()
        assert "exceeds maximum limit" in body["error"]

    def test_publish_failure_returns_503(self, client, mock_producer):
        mock_producer.publish_raw.side_effect = RuntimeError("broker down")

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps({"schema_version": "1.0"}),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "Kafka publish failed"
