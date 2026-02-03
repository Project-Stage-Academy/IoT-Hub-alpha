import pytest

from tests.utils.api import assert_pagination_envelope


@pytest.mark.django_db
def test_list_telemetry_success(api_client, auth_headers, telemetry_factory):
    telemetry_factory()

    response = api_client.get("/api/v1/telemetry", **auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert_pagination_envelope(payload)


@pytest.mark.django_db
def test_ingest_telemetry_single_success(api_client, device):
    payload = {"schema_version": "1.0", "value": 2443}
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry",
        data=payload,
        content_type="application/json",
        **headers,
    )

    assert response.status_code == 202


@pytest.mark.django_db
def test_ingest_telemetry_single_missing_header(api_client):
    payload = {"schema_version": "1.0", "value": 2443}

    response = api_client.post(
        "/api/v1/telemetry",
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_ingest_telemetry_single_invalid_payload(api_client, device):
    payload = {"schema_version": "1.0"}
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry",
        data=payload,
        content_type="application/json",
        **headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_ingest_telemetry_batch_success(api_client, device):
    payload = [
        {"schema_version": "1.0", "value": 2443},
        {"schema_version": "1.0", "value": 2444},
    ]
    headers = {"HTTP_X_DEVICE_SERIAL_NUMBER": device.serial_number}

    response = api_client.post(
        "/api/v1/telemetry/batch",
        data=payload,
        content_type="application/json",
        **headers,
    )

    assert response.status_code in {200, 202}


@pytest.mark.django_db
def test_ingest_telemetry_batch_missing_header(api_client):
    payload = [{"schema_version": "1.0", "value": 2443}]

    response = api_client.post(
        "/api/v1/telemetry/batch",
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400
