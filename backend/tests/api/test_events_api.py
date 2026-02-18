import pytest

from tests.utils.api import assert_pagination_envelope


@pytest.mark.django_db
def test_list_events_success(api_client, auth_headers, event):
    response = api_client.get("/api/v1/events", **auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert_pagination_envelope(payload)


@pytest.mark.django_db
def test_ack_event_success(api_client, auth_headers, event):
    response = api_client.post(
        f"/api/v1/events/{event.id}/ack",
        data={"status": "acknowledged"},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code in {200, 204}


@pytest.mark.django_db
def test_ack_event_error_missing_event(api_client, auth_headers):
    response = api_client.post(
        "/api/v1/events/999999/ack",
        data={"status": "acknowledged"},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 404
