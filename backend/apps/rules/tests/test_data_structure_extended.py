"""Extended tests for data_structure validation.

Covers NormalizedRecipient and Condition validation.
"""

import pytest
from pydantic import ValidationError

from apps.rules.services.data_structure import (
    NormalizedRecipient,
    Condition,
    EvalResults,
)


class TestNormalizedRecipient:
    """Test NormalizedRecipient model with validator coverage."""

    def test_normalized_recipient_sms_with_phone(self):
        """Create SMS recipient using phone field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "sms",
                "phone": "+1234567890",
            }
        )

        assert recipient.type == "sms"
        assert recipient.target == "+1234567890"

    def test_normalized_recipient_sms_with_target(self):
        """Create SMS recipient using target field directly."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "sms",
                "target": "+1234567890",
            }
        )

        assert recipient.type == "sms"
        assert recipient.target == "+1234567890"

    def test_normalized_recipient_sms_with_name(self):
        """Create SMS recipient with optional name field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "sms",
                "phone": "+1234567890",
                "name": "John Doe",
            }
        )

        assert recipient.type == "sms"
        assert recipient.target == "+1234567890"
        assert recipient.name == "John Doe"

    def test_normalized_recipient_sms_missing_phone_and_target(self):
        """SMS recipient must have phone or target."""
        with pytest.raises(ValueError, match="Missing 'phone'"):
            NormalizedRecipient.model_validate(
                {
                    "type": "sms",
                }
            )

    def test_normalized_recipient_email_with_address(self):
        """Create email recipient using address field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "email",
                "address": "user@example.com",
            }
        )

        assert recipient.type == "email"
        assert recipient.target == "user@example.com"

    def test_normalized_recipient_email_with_target(self):
        """Create email recipient using target field directly."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "email",
                "target": "user@example.com",
            }
        )

        assert recipient.type == "email"
        assert recipient.target == "user@example.com"

    def test_normalized_recipient_email_with_name(self):
        """Create email recipient with optional name field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "email",
                "address": "user@example.com",
                "name": "John Doe",
            }
        )

        assert recipient.type == "email"
        assert recipient.target == "user@example.com"
        assert recipient.name == "John Doe"

    def test_normalized_recipient_email_missing_address_and_target(self):
        """Email recipient must have address or target."""
        with pytest.raises(ValueError, match="Missing 'address'"):
            NormalizedRecipient.model_validate(
                {
                    "type": "email",
                }
            )

    def test_normalized_recipient_webhook_with_url(self):
        """Create webhook recipient using url field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "webhook",
                "url": "https://example.com/webhook",
            }
        )

        assert recipient.type == "webhook"
        assert recipient.target == "https://example.com/webhook"

    def test_normalized_recipient_webhook_with_target(self):
        """Create webhook recipient using target field directly."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "webhook",
                "target": "https://example.com/webhook",
            }
        )

        assert recipient.type == "webhook"
        assert recipient.target == "https://example.com/webhook"

    def test_normalized_recipient_webhook_with_name(self):
        """Create webhook recipient with optional name field."""
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "webhook",
                "url": "https://example.com/webhook",
                "name": "Alert Service",
            }
        )

        assert recipient.type == "webhook"
        assert recipient.target == "https://example.com/webhook"
        assert recipient.name == "Alert Service"

    def test_normalized_recipient_webhook_missing_url_and_target(self):
        """Webhook recipient must have url or target."""
        with pytest.raises(ValueError, match="Missing 'url'"):
            NormalizedRecipient.model_validate(
                {
                    "type": "webhook",
                }
            )

    def test_normalized_recipient_invalid_type(self):
        """Invalid recipient type raises validation error."""
        with pytest.raises(ValidationError):
            NormalizedRecipient.model_validate(
                {
                    "type": "invalid_type",
                    "target": "something",
                }
            )

    def test_normalized_recipient_target_overrides_derived(self):
        """If target is provided, it takes precedence.

        Precedence over derived field.
        """
        recipient = NormalizedRecipient.model_validate(
            {
                "type": "sms",
                "phone": "+1111111111",
                "target": "+2222222222",
            }
        )

        # target explicitly provided takes precedence
        assert recipient.target == "+2222222222"


class TestConditionValidatorMissingLines:
    """Test Condition validator to cover line 76 and 79."""

    def test_condition_and_with_operator_raises_error(self):
        """AND node with operator raises specific error."""
        with pytest.raises(ValidationError) as exc_info:
            Condition.model_validate(
                {
                    "type": "and",
                    "operator": "gt",
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    ],
                }
            )

        # Should contain the error message from line 76
        assert "cannot have operator/threshold" in str(exc_info.value)

    def test_condition_or_with_threshold_raises_error(self):
        """OR node with threshold raises specific error."""
        with pytest.raises(ValidationError) as exc_info:
            Condition.model_validate(
                {
                    "type": "or",
                    "threshold": 30.0,
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    ],
                }
            )

        # Should contain the error message from line 76
        assert "cannot have operator/threshold" in str(exc_info.value)

    def test_condition_leaf_with_only_occurrences_raises_error(self):
        """Leaf node with only occurrences.

        Missing window_seconds raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 25.0,
                    "occurrences": 3,
                    # missing window_seconds
                }
            )

        # Should contain the error message from line 79
        assert "must be set together" in str(exc_info.value)

    def test_condition_leaf_with_only_window_seconds_raises_error(self):
        """Leaf node with only window_seconds.

        Missing occurrences raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 25.0,
                    "window_seconds": 60,
                    # missing occurrences
                }
            )

        # Should contain the error message from line 79
        assert "must be set together" in str(exc_info.value)

    def test_condition_and_with_both_operator_and_threshold(self):
        """AND node with both operator and threshold raises error."""
        with pytest.raises(ValidationError) as exc_info:
            Condition.model_validate(
                {
                    "type": "and",
                    "operator": "gt",
                    "threshold": 25.0,
                    "conditions": [
                        {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    ],
                }
            )

        assert "cannot have operator/threshold" in str(exc_info.value)


class TestEvalResults:
    """Test EvalResults dataclass."""

    def test_eval_results_basic(self):
        """Create basic EvalResults."""
        from datetime import datetime

        now = datetime.now()
        results = EvalResults(
            trigger=True,
            values=[25.5, 26.0],
            start=now,
            end=now,
        )

        assert results.trigger is True
        assert results.values == [25.5, 26.0]
        assert results.start == now
        assert results.end == now

    def test_eval_results_to_dict(self):
        """Test EvalResults.to_dict() serialization."""
        from datetime import datetime

        start = datetime(2026, 2, 24, 10, 0, 0)
        end = datetime(2026, 2, 24, 10, 1, 0)

        results = EvalResults(
            trigger=True,
            values=[25.5],
            start=start,
            end=end,
        )

        serialized = results.to_dict()

        assert serialized["values"] == [25.5]
        assert serialized["start"] == "2026-02-24T10:00:00"
        assert serialized["end"] == "2026-02-24T10:01:00"

    def test_eval_results_to_dict_with_none_values(self):
        """Test EvalResults.to_dict() with None timestamps."""
        results = EvalResults(
            trigger=False,
            values=[],
            start=None,
            end=None,
        )

        serialized = results.to_dict()

        assert serialized["values"] == []
        assert serialized["start"] is None
        assert serialized["end"] is None

    def test_eval_results_defaults(self):
        """Test EvalResults default values."""
        results = EvalResults()

        assert results.trigger is False
        assert results.values == []
        assert results.start is None
        assert results.end is None

    def test_eval_results_to_dict_empty(self):
        """Test EvalResults.to_dict() with defaults."""
        results = EvalResults()
        serialized = results.to_dict()

        assert serialized["values"] == []
        assert serialized["start"] is None
        assert serialized["end"] is None
