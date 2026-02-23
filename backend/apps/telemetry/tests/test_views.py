import json
<<<<<<< Updated upstream
import pytest
from unittest.mock import patch
from apps.telemetry.models import Telemetry
=======
from unittest.mock import MagicMock, patch
>>>>>>> Stashed changes

import pytest


<<<<<<< Updated upstream
@pytest.mark.django_db
class TestTelemetryIngestionSyncMode:

    def test_single_ingestion_success(self, sync_mode, client, device):
        payload = {
            "schema_version": "1.0",
            "value": 2550,
        }
=======
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
>>>>>>> Stashed changes

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

<<<<<<< Updated upstream
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert "id" in data
        assert data["device_id"] == str(device.id)
        assert "timestamp" in data

        assert Telemetry.objects.count() == 1
        telemetry = Telemetry.objects.first()
        assert telemetry.device == device
        assert telemetry.payload["schema_version"] == "1.0"
        assert telemetry.payload["value"] == 25.5
        assert telemetry.payload["serial_number"] == device.serial_number

    def test_single_ingestion_with_idempotency_key(self, sync_mode, client, device):
        payload = {
            "schema_version": "1.0",
        }
=======
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["count"] == 1
        assert body["topic"] == "telemetry.raw"
        assert body["pipeline_mode"] == "kafka"
        mock_producer.publish_raw.assert_called_once()
        mock_producer.publish_raw_batch.assert_not_called()

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
>>>>>>> Stashed changes

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
            HTTP_IDEMPOTENCY_KEY="  test-key-123  ",
        )

<<<<<<< Updated upstream
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["idempotency_key"] == "test-key-123"

    def test_single_ingestion_missing_header(self, sync_mode, client):
        payload = {"schema_version": "1.0"}

=======
        assert response.status_code == 202
        body = response.json()
        assert body["idempotency_key"] == "test-key-123"
        call_kwargs = mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["data"]["idempotency_key"] == "test-key-123"

    def test_missing_serial_number_header(self, client):
>>>>>>> Stashed changes
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps({"schema_version": "1.0"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        body = response.json()
        assert "X-Device-Serial-Number header is required" in body["error"]

    def test_single_ingestion_missing_schema_version(self, sync_mode, client, device):
        payload = {}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "schema_version" in data["details"]

    def test_single_ingestion_nonexistent_device(self, sync_mode, client):
        payload = {
            "schema_version": "1.0",
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER="NONEXISTENT999",
        )

        assert response.status_code == 400
        data = response.json()
        assert "device" in data["details"]

    def test_single_ingestion_invalid_json(self, sync_mode, client):
        response = client.post(
            "/api/v1/telemetry/", data="not valid json", content_type="application/json"
        )

        assert response.status_code == 400
        body = response.json()
        assert "Invalid JSON payload" in body["error"]

<<<<<<< Updated upstream
    def test_batch_ingestion_success(self, sync_mode, client, device):
        payload = [
            {
                "schema_version": "1.0",
                "value": 100,
            },
            {
                "schema_version": "1.0",
                "value": 200,
            },
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["count"] == 2
        assert len(data["ids"]) == 2
        assert data["summary"]["total"] == 2
        assert data["summary"]["successful"] == 2
        assert data["summary"]["failed"] == 0

        assert Telemetry.objects.count() == 2

    def test_batch_ingestion_empty_batch(self, sync_mode, client, device):
=======
    def test_empty_batch(self, client):
>>>>>>> Stashed changes
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps([]),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 400
        body = response.json()
        assert "Empty batch" in body["error"]

<<<<<<< Updated upstream
    def test_batch_ingestion_exceeds_limit(self, sync_mode, client, device):
        payload = [{"schema_version": "1.0"}] * 1001
=======
    def test_batch_exceeds_limit(self, client, settings):
        settings.TELEMETRY_MAX_BATCH_SIZE = 2
        payload = [{"schema_version": "1.0"}] * 3
>>>>>>> Stashed changes

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=self.serial_number,
        )

        assert response.status_code == 400
<<<<<<< Updated upstream
        data = response.json()
        assert "exceeds maximum limit" in data["error"]

    def test_batch_ingestion_validation_errors_all_or_nothing(
        self, sync_mode, client, device
    ):
        payload = [
            {
                "schema_version": "1.0",
                "value": 100,
            },
            {},
            {
                "schema_version": "1.0",
                "value": 300,
            },
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Batch ingestion failed" in data["error"]
        assert data["details"]["summary"]["total"] == 3
        assert data["details"]["summary"]["successful"] == 0
        assert data["details"]["summary"]["failed"] == 1
        assert len(data["details"]["errors"]) == 1

        assert Telemetry.objects.count() == 0

    def test_batch_ingestion_with_idempotency_key(self, sync_mode, client, device):
        payload = [{"schema_version": "1.0"}]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
            HTTP_IDEMPOTENCY_KEY="batch-test-key",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["idempotency_key"] == "batch-test-key"

    def test_single_ingestion_with_optional_timestamp(self, sync_mode, client, device):
        """Test that timestamp field is accepted in payload (stored in server time)."""
        payload = {
            "schema_version": "1.0",
            "timestamp": "2024-01-15T10:30:00Z",
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert Telemetry.objects.count() == 1


@pytest.mark.django_db
class TestTelemetryIngestionAsyncMode:

    @patch("apps.telemetry.views.ingest_telemetry_batch_async")
    def test_single_ingestion_async(self, mock_task, async_mode, client, device):
        mock_task.delay.return_value.id = "test-task-id-123"

        payload = {
            "schema_version": "1.0",
            "value": 2550,
        }

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "request_id" in data
        assert data["count"] == 1
        assert data["task_id"] == "test-task-id-123"

        assert Telemetry.objects.count() == 0
        mock_task.delay.assert_called_once()

    @patch("apps.telemetry.views.ingest_telemetry_batch_async")
    def test_batch_ingestion_async(self, mock_task, async_mode, client, device):
        mock_task.delay.return_value.id = "test-batch-task-id"

        payload = [
            {
                "schema_version": "1.0",
                "value": 100,
            },
            {
                "schema_version": "1.0",
                "value": 200,
            },
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 2
        assert "request_id" in data
        assert data["task_id"] == "test-batch-task-id"

        assert Telemetry.objects.count() == 0
        mock_task.delay.assert_called_once()

    def test_async_validation_happens_before_queueing(self, async_mode, client, device):
        payload = [
            {"schema_version": "1.0"},
            {},
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Validation failed" in data["error"]
        assert data["details"]["summary"]["failed"] == 1
        assert Telemetry.objects.count() == 0
=======
        body = response.json()
        assert "exceeds maximum limit" in body["error"]
>>>>>>> Stashed changes
