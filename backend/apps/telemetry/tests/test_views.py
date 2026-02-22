import json
import pytest
from unittest.mock import patch, MagicMock
from apps.telemetry.models import Telemetry
from apps.telemetry.views import TelemetryIngestView
from apps.telemetry.kafka import KafkaProducerError
from django.test import TestCase, RequestFactory, override_settings


@pytest.mark.django_db
class TestTelemetryIngestionSyncMode:
    @pytest.fixture(autouse=True)
    def _setup_settings(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "direct"
        settings.TELEMETRY_ASYNC_INGESTION = False

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
    @pytest.fixture(autouse=True)
    def _setup_settings(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "direct"
        settings.TELEMETRY_ASYNC_INGESTION = True

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


class TestTelemetryIngestViewKafka:
    @pytest.fixture(autouse=True)
    def setup_env(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "kafka"

        self.factory = RequestFactory()
        self.view = TelemetryIngestView.as_view()
        self.url = "/api/v1/telemetry/"

        self.valid_data = {"schema_version": "1.0", "value": 42}
        self.headers = {
            "HTTP_X_DEVICE_SERIAL_NUMBER": "TEST-SN-001",
            "HTTP_IDEMPOTENCY_KEY": "idem-key-999",
        }

    @patch("apps.telemetry.views.TelemetryKafkaProducer")
    @patch("apps.telemetry.views.TelemetryValidator.validate_batch")
    def test_handle_kafka_success(self, mock_validate, MockProducer):
        """
        Checks that valid data is processed correctly:
        validation, envelope construction, and Kafka publishing.
        """

        mock_validate.return_value = ([self.valid_data], [])

        mock_producer_instance = MagicMock()
        mock_producer_instance.resolve_topic.return_value = (
            "telemetry.device.TEST-SN-001"
        )
        MockProducer.return_value = mock_producer_instance

        request = self.factory.post(
            self.url,
            data=json.dumps(self.valid_data),
            content_type="application/json",
            **self.headers,
        )
        response = self.view(request)

        assert response.status_code == 202
        response_data = json.loads(response.content)
        assert response_data["status"] == "accepted"
        assert response_data["topic"] == "telemetry.device.TEST-SN-001"
        assert response_data["idempotency_key"] == "idem-key-999"
        assert response_data["pipeline_mode"] == "kafka"
        assert "request_id" in response_data

        mock_producer_instance.publish_batch.assert_called_once()
        args, kwargs = mock_producer_instance.publish_batch.call_args
        kafka_messages = args[0]

        assert len(kafka_messages) == 1
        msg = kafka_messages[0]
        assert msg["ingest_protocol"] == "http"
        assert msg["serial_number"] == "TEST-SN-001"

        expected_payload = self.valid_data.copy()
        expected_payload["serial_number"] = "TEST-SN-001"
        assert msg["payload"] == expected_payload

        assert msg["ingest_index"] == 0
        assert "received_at" in msg
        assert "request_id" in msg

    @patch("apps.telemetry.views.TelemetryKafkaProducer")
    @patch("apps.telemetry.views.TelemetryValidator.validate_batch")
    def test_handle_kafka_validation_error(self, mock_validate, MockProducer):
        """
        Checks that invalid data is rejected before
        any Kafka publishing occurs.
        """
        mock_validate.return_value = ([], [{"error": "Missing schema", "index": 0}])

        request = self.factory.post(
            self.url,
            data=json.dumps({"bad": "data"}),
            content_type="application/json",
            **self.headers,
        )
        response = self.view(request)

        assert response.status_code == 400
        response_data = json.loads(response.content)
        assert "Validation failed" in response_data.get("error", "")

        MockProducer.assert_not_called()

    @patch("apps.telemetry.views.TelemetryKafkaProducer")
    @patch("apps.telemetry.views.TelemetryValidator.validate_batch")
    def test_handle_kafka_producer_error(self, mock_validate, MockProducer):
        """
        Checks that if the Kafka broker is unavailable,
        the error is handled correctly.
        """
        mock_validate.return_value = ([self.valid_data], [])

        mock_producer_instance = MagicMock()
        mock_producer_instance.publish_batch.side_effect = KafkaProducerError(
            "Connection timeout"
        )
        MockProducer.return_value = mock_producer_instance

        request = self.factory.post(
            self.url,
            data=json.dumps(self.valid_data),
            content_type="application/json",
            **self.headers,
        )
        response = self.view(request)

        assert response.status_code == 503
        response_data = json.loads(response.content)
        assert response_data["error"] == "Kafka publish failed"
        assert "Connection timeout" in response_data["details"]
