import pytest

from tests.utils.api import assert_pagination_envelope


@pytest.mark.django_db
def test_list_devices_success(api_client, auth_headers, sample_devices):
    response = api_client.get("/api/v1/devices/", **auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert_pagination_envelope(payload)


@pytest.mark.django_db
def test_create_device_success(api_client, auth_headers, device_type):
    payload = {
        "name": "Temp Sensor A",
        "serial_number": "SN-900001",
        "location": "Plant 9",
        "status": "active",
        "device_type_id": str(device_type.id),
    }

    response = api_client.post(
        "/api/v1/devices/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == payload["name"]
    assert data["serial_number"] == payload["serial_number"]


@pytest.mark.django_db
def test_create_device_error_missing_required_fields(api_client, auth_headers):
    response = api_client.post(
        "/api/v1/devices/",
        data={},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_device_invalid_serial_number_duplicate(
    api_client, auth_headers, device, device_type
):
    payload = {
        "name": "Temp Sensor Dup",
        "serial_number": device.serial_number,
        "location": "Plant 9",
        "status": "active",
        "device_type_id": str(device_type.id),
    }

    response = api_client.post(
        "/api/v1/devices/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_device_invalid_device_type(api_client, auth_headers):
    payload = {
        "name": "Temp Sensor Bad Type",
        "serial_number": "SN-900002",
        "location": "Plant 9",
        "status": "active",
        "device_type_id": "00000000-0000-0000-0000-000000000000",
    }

    response = api_client.post(
        "/api/v1/devices/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_get_device_success(api_client, auth_headers, device):
    response = api_client.get(f"/api/v1/devices/{device.id}/", **auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == device.name


@pytest.mark.django_db
def test_update_device_success(api_client, auth_headers, device):
    payload = {"location": "Plant 99"}

    response = api_client.patch(
        f"/api/v1/devices/{device.id}/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_update_device_not_found(api_client, auth_headers):
    payload = {"location": "Plant 99"}

    response = api_client.patch(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_device_success(api_client, auth_headers, device):
    response = api_client.delete(f"/api/v1/devices/{device.id}/", **auth_headers)

    assert response.status_code == 204


@pytest.mark.django_db
def test_delete_device_not_found(api_client, auth_headers):
    response = api_client.delete(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000/",
        **auth_headers,
    )

    assert response.status_code == 404
