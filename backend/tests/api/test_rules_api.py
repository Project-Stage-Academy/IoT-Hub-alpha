import pytest


@pytest.mark.django_db
def test_create_rule_success(api_client, auth_headers, device):
    payload = {
        "device_id": str(device.id),
        "name": "High Temp",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 75.0},
        "action_config": [{"type": "notification", "template_id": 1}],
        "is_enabled": True,
    }

    response = api_client.post(
        "/api/v1/rules",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code in {200, 201}


@pytest.mark.django_db
def test_create_rule_error_invalid_payload(api_client, auth_headers, device):
    payload = {
        "device_id": str(device.id),
        "name": "High Temp",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 75.0},
        "action_config": [{"type": "notification"}],
    }

    response = api_client.post(
        "/api/v1/rules",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_enable_rule_success(api_client, auth_headers, rule):
    response = api_client.patch(
        f"/api/v1/rules/{rule.id}/enable",
        data={"is_enabled": True},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code in {200, 204}


@pytest.mark.django_db
def test_enable_rule_error_missing_rule(api_client, auth_headers):
    response = api_client.patch(
        "/api/v1/rules/00000000-0000-0000-0000-000000000000/enable",
        data={"is_enabled": True},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 404
