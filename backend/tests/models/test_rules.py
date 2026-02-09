import pytest
from django.core.exceptions import ValidationError

from apps.rules.models import Rule


@pytest.mark.django_db
def test_create_rule(rule, device):
    assert rule.pk is not None
    assert rule.device == device
    assert rule.is_enabled is True
    assert Rule.objects.count() == 1


@pytest.mark.django_db
def test_rule_str(rule, device):
    assert str(rule) == f"{rule.name} - {device.name}"


@pytest.mark.django_db
def test_rule_action_config_validation_rejects_non_list(device):
    rule = Rule(
        device=device,
        name="Bad Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config="not-a-list",
    )

    with pytest.raises(ValidationError):
        rule.full_clean()


@pytest.mark.django_db
def test_rule_action_config_validation_requires_type(device):
    rule = Rule(
        device=device,
        name="Bad Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"template_id": 1}],
    )

    with pytest.raises(ValidationError):
        rule.full_clean()


@pytest.mark.django_db
def test_rule_action_config_validation_notification_requires_template(device):
    rule = Rule(
        device=device,
        name="Bad Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification"}],
    )

    with pytest.raises(ValidationError):
        rule.full_clean()


@pytest.mark.django_db
def test_rule_action_config_validation_cooldown_non_negative(device):
    rule = Rule(
        device=device,
        name="Bad Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[
            {"type": "notification", "template_id": 1, "cooldown_minutes": -1}
        ],
    )

    with pytest.raises(ValidationError):
        rule.full_clean()
