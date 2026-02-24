"""Additional tests for data_structure validation coverage."""

import pytest
from pydantic import ValidationError

from apps.rules.services.data_structure import Condition, ActionConfig


class TestConditionValidation:
    """Test Condition model validation edge cases."""

    def test_condition_with_none_threshold(self):
        """Condition with None threshold raises validation error."""
        with pytest.raises(ValidationError):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": None,
                }
            )

    def test_condition_with_missing_operator(self):
        """Condition without operator raises validation error."""
        with pytest.raises(ValidationError):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "threshold": 25.0,
                }
            )

    def test_condition_with_invalid_operator(self):
        """Condition with invalid operator raises validation error."""
        with pytest.raises(ValidationError):
            Condition.model_validate(
                {
                    "type": "leaf",
                    "operator": "invalid_op",
                    "threshold": 25.0,
                }
            )

    def test_condition_leaf_with_valid_data(self):
        """Condition leaf with all valid data."""
        cond = Condition.model_validate(
            {
                "type": "leaf",
                "operator": "gt",
                "threshold": 25.0,
                "occurrences": 3,
                "window_seconds": 60,
            }
        )
        assert cond.operator == "gt"
        assert cond.threshold == 25.0

    def test_condition_and_operator_with_conditions(self):
        """Condition with AND operator and sub-conditions."""
        cond = Condition.model_validate(
            {
                "type": "and",
                "conditions": [
                    {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    {"type": "leaf", "operator": "lt", "threshold": 30.0},
                ],
            }
        )
        assert cond.type == "and"
        assert len(cond.conditions) == 2

    def test_condition_or_operator_with_conditions(self):
        """Condition with OR operator and sub-conditions."""
        cond = Condition.model_validate(
            {
                "type": "or",
                "conditions": [
                    {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    {"type": "leaf", "operator": "lt", "threshold": 15.0},
                ],
            }
        )
        assert cond.type == "or"
        assert len(cond.conditions) == 2


class TestActionConfigValidation:
    """Test ActionConfig model validation."""

    def test_action_config_notification_valid(self):
        """ActionConfig with notification type."""
        config = ActionConfig.model_validate(
            {
                "type": "notification",
                "template_id": 1,
            }
        )
        assert config.type == "notification"
        assert config.template_id == 1

    def test_action_config_stop_machine_valid(self):
        """ActionConfig with stop_machine type."""
        config = ActionConfig.model_validate(
            {
                "type": "stop_machine",
            }
        )
        assert config.type == "stop_machine"

    def test_action_config_invalid_type(self):
        """ActionConfig with invalid type raises error."""
        with pytest.raises(ValidationError):
            ActionConfig.model_validate(
                {
                    "type": "invalid_type",
                }
            )

    def test_action_config_template_id_optional(self):
        """ActionConfig template_id is optional."""
        config = ActionConfig.model_validate(
            {
                "type": "stop_machine",
            }
        )
        assert config.template_id is None
