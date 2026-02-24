import json
import pytest
from unittest.mock import patch, MagicMock
from apps.telemetry.models import Telemetry
from apps.telemetry.views import TelemetryIngestView
from apps.telemetry.kafka import KafkaProducerError, KafkaPublishError
from django.db import DatabaseError, IntegrityError


@pytest.mark.django_db
class TestTelemetryIngestionSyncMode:
    @pytest.fixture(autouse=True)
    def _setup_settings(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "direct"
        settings.TELEMETRY_ASYNC_INGESTION = False

    def test_single_ingestion_sync(self, client, device):
        """Checks successful saving of a single record directly to the database"""
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
        assert Telemetry.objects.count() == 1

    def test_batch_ingestion_sync(self, client, device):
        """
        Checks successful saving of a batch
        of records directly to the database
        """
        payload = [
            {"schema_version": "1.0", "value": 100},
            {"schema_version": "1.0", "value": 200},
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
        assert Telemetry.objects.count() == 2

    def test_sync_validation_happens_before_saving(self, client, device):
        """Checks that invalid data is not stored in the database"""
        payload = {"value": 2550}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        assert Telemetry.objects.count() == 0


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


@pytest.mark.django_db
class TestTelemetryIngestViewKafka:

    def test_single_payload_published(self, client, mock_producer, device):
        payload = {"schema_version": "1.0", "value": 2550}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["count"] == 1
        assert body["topic"] == "telemetry.raw"
        assert body["pipeline_mode"] == "kafka"
        assert body["idempotency_key"].startswith("http:")
        mock_producer.publish_raw.assert_called_once()
        mock_producer.publish_raw_batch.assert_not_called()

        call_kwargs = mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["serial_number"] == device.serial_number
        assert call_kwargs["source"] == "http"
        assert call_kwargs["data"]["serial_number"] == device.serial_number
        assert call_kwargs["data"]["ingest_protocol"] == "http"
        assert call_kwargs["data"]["idempotency_key"] == body["idempotency_key"]

    def test_batch_payload_uses_publish_raw_batch(self, client, mock_producer, device):
        payload = [
            {"schema_version": "1.0", "value": 100},
            {"schema_version": "1.0", "value": 200},
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert body["count"] == 2
        mock_producer.publish_raw_batch.assert_called_once()
        mock_producer.publish_raw.assert_not_called()

        call_kwargs = mock_producer.publish_raw_batch.call_args.kwargs
        assert call_kwargs["serial_number"] == device.serial_number
        assert call_kwargs["source"] == "http"
        assert len(call_kwargs["data"]) == 2
        for event in call_kwargs["data"]:
            assert event["serial_number"] == device.serial_number
            assert event["ingest_protocol"] == "http"
            assert event["idempotency_key"].startswith(f"{body['idempotency_key']}:")

        idempotency_keys = [event["idempotency_key"] for event in call_kwargs["data"]]
        assert len(set(idempotency_keys)) == 2

    def test_idempotency_key_is_trimmed_and_passed(self, client, mock_producer, device):
        payload = {"schema_version": "1.0", "value": 1}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
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

    def test_empty_batch(self, client, device):
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps([]),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        body = response.json()
        assert "Empty batch" in body["error"]

    def test_batch_exceeds_limit(self, client, settings, device):
        settings.TELEMETRY_MAX_BATCH_SIZE = 2
        payload = [{"schema_version": "1.0"}] * 3

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        body = response.json()
        assert "exceeds maximum limit" in body["error"]

    def test_publish_failure_returns_503(self, client, mock_producer, device):
        mock_producer.publish_raw.side_effect = KafkaPublishError("broker down")

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps({"schema_version": "1.0"}),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "Kafka publish failed"
        assert "details" not in body

    def test_idempotency_integrity_error_returns_409(self):
        view = TelemetryIngestView()
        response = view._handle_db_errors(
            IntegrityError(
                (
                    "duplicate key value violates unique constraint "
                    '"telemetry_idempotency_key_key"'
                )
            ),
            "single sync ingestion",
        )

        assert response.status_code == 409

    def test_non_idempotency_integrity_error_returns_500(self):
        view = TelemetryIngestView()
        response = view._handle_db_errors(
            IntegrityError(
                (
                    "duplicate key value violates unique constraint "
                    '"telemetry_device_id_timestamp_key"'
                )
            ),
            "batch sync ingestion",
        )

        assert response.status_code == 500


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

    def test_database_error_returns_500(self):
        view = TelemetryIngestView()
        response = view._handle_db_errors(
            DatabaseError("connection lost"),
            "single sync ingestion",
        )

        assert response.status_code == 500
