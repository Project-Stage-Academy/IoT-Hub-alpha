import pytest

from tests.utils.api import assert_pagination_envelope


@pytest.mark.django_db
def test_list_devices_success(api_client, auth_headers, sample_devices):
    response = api_client.get("/api/v1/devices", **auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert_pagination_envelope(payload)


@pytest.mark.django_db
def test_create_device_success(api_client, auth_headers):
    payload = {
        "name": "Temp Sensor A",
        "ssn": "SN-900001",
        "location": "Plant 9",
        "status": "Active",
        "description": "Gen 2 sensor",
        "default_metrics": "C",
    }

    response = api_client.post(
        "/api/v1/devices", data=payload, content_type="application/json", **auth_headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["ssn"] == payload["ssn"]


@pytest.mark.django_db
def test_create_device_error_missing_required_fields(api_client, auth_headers):
    response = api_client.post(
        "/api/v1/devices", data={}, content_type="application/json", **auth_headers
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_get_device_success(api_client, auth_headers, device):
    response = api_client.get(f"/api/v1/devices/{device.id}", **auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == device.name


@pytest.mark.django_db
def test_update_device_success(api_client, auth_headers, device):
    payload = {"location": "Plant 99"}

    response = api_client.put(
        f"/api/v1/devices/{device.id}",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_delete_device_success(api_client, auth_headers, device):
    response = api_client.delete(f"/api/v1/devices/{device.id}", **auth_headers)

    assert response.status_code in {200, 204}
