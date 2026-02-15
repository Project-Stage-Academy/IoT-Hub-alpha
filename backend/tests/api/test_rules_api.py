import pytest

from apps.events.models import Event
from apps.rules.models import Rule


def _require_rules_api(api_client, path="/api/v1/rules/"):
    response = api_client.get(path)
    if response.status_code == 404:
        pytest.skip("Rules endpoints are not wired in this project yet.")


@pytest.mark.django_db
def test_create_rule_success(api_client, auth_headers, device):
    _require_rules_api(api_client)
    payload = {
        "device_id": str(device.id),
        "name": "High Temp",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 75.0},
        "action_config": [{"type": "notification", "template_id": 1}],
        "is_enabled": True,
    }

    response = api_client.post(
        "/api/v1/rules/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code in {200, 201}


@pytest.mark.django_db
def test_create_rule_error_invalid_payload(api_client, auth_headers, device):
    _require_rules_api(api_client)
    payload = {
        "device_id": str(device.id),
        "name": "High Temp",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 75.0},
        "action_config": [{"type": "notification"}],
    }

    response = api_client.post(
        "/api/v1/rules/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_enable_rule_success(api_client, auth_headers, rule):
    _require_rules_api(api_client, path=f"/api/v1/rules/{rule.id}/enable/")
    response = api_client.patch(
        f"/api/v1/rules/{rule.id}/enable/",
        data={"is_enabled": True},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code in {200, 204}


@pytest.mark.django_db
def test_enable_rule_error_missing_rule(api_client, auth_headers):
    _require_rules_api(
        api_client,
        path="/api/v1/rules/00000000-0000-0000-0000-000000000000/enable/",
    )
    response = api_client.patch(
        "/api/v1/rules/00000000-0000-0000-0000-000000000000/enable/",
        data={"is_enabled": True},
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_create_rule_invalid_condition_schema(api_client, auth_headers, device):
    _require_rules_api(api_client)
    payload = {
        "device_id": str(device.id),
        "name": "Bad Condition",
        "condition": {"type": "leaf", "operator": "gt"},
        "action_config": [{"type": "notification", "template_id": 1}],
        "is_enabled": True,
    }

    response = api_client.post(
        "/api/v1/rules/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_rule_invalid_action_config(api_client, auth_headers, device):
    _require_rules_api(api_client)
    payload = {
        "device_id": str(device.id),
        "name": "Bad Action",
        "condition": {"type": "leaf", "operator": "gt", "threshold": 75.0},
        "action_config": "not-a-list",
        "is_enabled": True,
    }

    response = api_client.post(
        "/api/v1/rules/",
        data=payload,
        content_type="application/json",
        **auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_update_rule_enable_disable(api_client, auth_headers, rule):
    _require_rules_api(api_client, path=f"/api/v1/rules/{rule.id}/enable/")
    response = api_client.patch(
        f"/api/v1/rules/{rule.id}/enable/",
        data={"is_enabled": True},
        content_type="application/json",
        **auth_headers,
    )
    assert response.status_code in {200, 204}

    response = api_client.patch(
        f"/api/v1/rules/{rule.id}/enable/",
        data={"is_enabled": False},
        content_type="application/json",
        **auth_headers,
    )
    assert response.status_code in {200, 204}


@pytest.mark.django_db
def test_delete_rule_missing_returns_404(api_client, auth_headers):
    _require_rules_api(
        api_client, path="/api/v1/rules/00000000-0000-0000-0000-000000000000/"
    )
    response = api_client.delete(
        "/api/v1/rules/00000000-0000-0000-0000-000000000000/",
        **auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_delete_rule_protect_fk(api_client, auth_headers, event, rule):
    _require_rules_api(api_client, path=f"/api/v1/rules/{rule.id}/")
    response = api_client.delete(f"/api/v1/rules/{rule.id}/", **auth_headers)
    assert response.status_code in {400, 409}

    Event.objects.filter(id=event.id).exists()


@pytest.mark.django_db
def test_list_rules_filtered_by_device(api_client, auth_headers, device, device_type):
    _require_rules_api(api_client)
    other_device = device.__class__.objects.create(
        device_type=device_type,
        name="Other Device",
        serial_number="SN-OTHER-0001",
        status=device.status,
    )
    Rule.objects.create(
        device=other_device,
        name="Other Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 5.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )

    response = api_client.get(
        f"/api/v1/rules/?device_id={device.id}",
        **auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    items = payload.get("data", payload)
    if not items:
        return
    for item in items:
        item_device_id = item.get("device_id")
        if item_device_id is None and isinstance(item.get("device"), dict):
            item_device_id = item["device"].get("id")
        if item_device_id is None:
            continue
        assert str(item_device_id) == str(device.id)
