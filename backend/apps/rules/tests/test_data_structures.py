import pytest
from pydantic import ValidationError

from apps.rules.services.data_structure import (
    NormalizedRecipient,
    Condition,
    ExternalEventMessage,
)


def test_normalized_recipient_derives_target_sms():
    r = NormalizedRecipient.model_validate({"type": "sms", "phone": "+380501234567"})
    assert r.target == "+380501234567"


def test_normalized_recipient_missing_phone_raises():
    with pytest.raises(ValueError) as e:
        NormalizedRecipient.model_validate({"type": "sms"})
    assert "Missing 'phone' for type 'sms'" in str(e.value)


def test_condition_leaf_requires_operator_and_threshold():
    with pytest.raises(ValidationError):
        Condition.model_validate({"type": "leaf"})


def test_condition_leaf_cannot_have_conditions():
    with pytest.raises(ValidationError):
        Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 1, "conditions": []}
        )


def test_condition_and_requires_non_empty_conditions():
    with pytest.raises(ValidationError):
        Condition.model_validate({"type": "and", "conditions": []})


def test_condition_and_cannot_have_operator_threshold():
    with pytest.raises(ValidationError):
        Condition.model_validate(
            {
                "type": "and",
                "operator": "gt",
                "threshold": 1,
                "conditions": [{"type": "leaf", "operator": "gt", "threshold": 1}],
            }
        )


def test_condition_occurrences_window_must_be_set_together():
    with pytest.raises(ValidationError):
        Condition.model_validate(
            {"type": "leaf", "operator": "gt", "threshold": 1, "occurrences": 2}
        )


def test_external_event_message_ignores_extra_fields():
    msg = ExternalEventMessage.model_validate(
        {
            "rule_id": "r1",
            "device_id": "d1",
            "extra_field": "ignored",
        }
    )
    dumped = msg.model_dump()
    assert dumped["rule_id"] == "r1"
    assert dumped["device_id"] == "d1"
    assert "extra_field" not in dumped
