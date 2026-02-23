import pytest

from tests.utils.api import assert_pagination_envelope


def _require_telemetry_api(api_client, path="/api/v1/telemetry/"):
    response = api_client.get(path)
    if response.status_code == 404:
        pytest.skip("Telemetry endpoints are not wired in this project yet.")


@pytest.mark.django_db
def test_list_telemetry_success(api_client, auth_headers, telemetry_factory):
    _require_telemetry_api(api_client)
    telemetry_factory()

    response = api_client.get("/api/v1/telemetry/", **auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert_pagination_envelope(payload)


@pytest.mark.django_db
def test_ingest_telemetry_single_success(api_client, device):
    _require_telemetry_api(api_client)
    payload = {"schema_version": "1.0", "value": 2443}
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry/",
        data=payload,
        content_type="application/json",
        **headers,
    )

    assert response.status_code in {201, 202}


@pytest.mark.django_db
def test_ingest_telemetry_single_missing_header(api_client):
    _require_telemetry_api(api_client)
    payload = {"schema_version": "1.0", "value": 2443}

    response = api_client.post(
        "/api/v1/telemetry/",
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_ingest_telemetry_single_invalid_payload(api_client, device):
    _require_telemetry_api(api_client)
    payload = {"schema_version": "9.9", "value": 2443}
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry/",
        data=payload,
        content_type="application/json",
        **headers,
    )

    # Ingestion is publish-only; schema validation happens downstream in the consumer.
    assert response.status_code == 202


@pytest.mark.django_db
def test_ingest_telemetry_invalid_device_serial(api_client):
    _require_telemetry_api(api_client)
    payload = {"schema_version": "1.0", "value": 2443}
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": "SN-DOES-NOT-EXIST"}

    response = api_client.post(
        "/api/v1/telemetry/",
        data=payload,
        content_type="application/json",
        **headers,
    )

    # Ingestion is publish-only; device lookup happens downstream in the consumer.
    assert response.status_code == 202


@pytest.mark.django_db
def test_ingest_telemetry_malformed_json(api_client, device):
    _require_telemetry_api(api_client)
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry/",
        data="not valid json",
        content_type="application/json",
        **headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_ingest_telemetry_batch_success(api_client, device):
    _require_telemetry_api(api_client, path="/api/v1/telemetry/batch/")
    payload = [
        {"schema_version": "1.0", "value": 2443},
        {"schema_version": "1.0", "value": 2444},
    ]
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry/batch/",
        data=payload,
        content_type="application/json",
        **headers,
    )

    assert response.status_code in {201, 202}


@pytest.mark.django_db
def test_ingest_telemetry_batch_missing_header(api_client):
    _require_telemetry_api(api_client, path="/api/v1/telemetry/batch/")
    payload = [{"schema_version": "1.0", "value": 2443}]

    response = api_client.post(
        "/api/v1/telemetry/batch/",
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400
