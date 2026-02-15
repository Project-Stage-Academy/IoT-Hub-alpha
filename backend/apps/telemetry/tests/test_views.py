import json
import pytest
from unittest.mock import patch
from apps.telemetry.models import Telemetry


@pytest.mark.django_db
class TestTelemetryIngestionSyncMode:

    def test_single_ingestion_success(self, sync_mode, client, device):
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

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
            HTTP_IDEMPOTENCY_KEY="test-key-123",
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["idempotency_key"] == "test-key-123"

    def test_single_ingestion_missing_header(self, sync_mode, client):
        payload = {"schema_version": "1.0"}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "X-Device-Serial-Number header is required" in data["error"]

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
        data = response.json()
        assert "Invalid JSON payload" in data["error"]

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
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps([]),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Empty batch" in data["error"]

    def test_batch_ingestion_exceeds_limit(self, sync_mode, client, device):
        payload = [{"schema_version": "1.0"}] * 1001

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
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
