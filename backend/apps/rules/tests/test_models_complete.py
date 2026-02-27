"""Complete coverage tests for Rule model validators and methods."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.devices.models import DeviceType, Device
from apps.rules.models import (
    Rule,
    validate_action_config,
    validate_condition,
)


@pytest.mark.django_db
class TestValidateActionConfig:
    """Test validate_action_config validator comprehensively."""

    def test_action_config_non_list(self):
        """Reject action_config that is not a list."""
        with pytest.raises(DjangoValidationError, match="must be a list"):
            validate_action_config({"type": "notification"})

    def test_action_config_empty_list(self):
        """Accept empty action_config list."""
        # Should not raise
        validate_action_config([])

    def test_action_config_item_not_dict(self):
        """Reject action_config items that are not dicts."""
        with pytest.raises(DjangoValidationError, match="must be a dictionary"):
            validate_action_config(["string_item"])

    def test_action_config_missing_type_field(self):
        """Reject action config items missing 'type' field."""
        with pytest.raises(DjangoValidationError, match="must have a 'type' field"):
            validate_action_config([{"cooldown_minutes": 60}])

    def test_action_config_cooldown_non_integer(self):
        """Reject cooldown_minutes that is not an integer."""
        with pytest.raises(
            DjangoValidationError, match="cooldown_minutes must be an integer"
        ):
            validate_action_config([{"type": "notification", "cooldown_minutes": "60"}])

    def test_action_config_cooldown_negative(self):
        """Reject negative cooldown_minutes."""
        with pytest.raises(
            DjangoValidationError, match="cooldown_minutes must be >= 0"
        ):
            validate_action_config([{"type": "notification", "cooldown_minutes": -5}])

    def test_action_config_cooldown_zero(self):
        """Accept zero cooldown_minutes."""
        # Should not raise
        validate_action_config(
            [{"type": "notification", "template_id": 5, "cooldown_minutes": 0}]
        )

    def test_action_config_cooldown_positive(self):
        """Accept positive cooldown_minutes."""
        # Should not raise
        validate_action_config(
            [{"type": "notification", "template_id": 5, "cooldown_minutes": 60}]
        )

    def test_action_config_notification_without_template_id(self):
        """Reject notification action without template_id."""
        with pytest.raises(
            DjangoValidationError,
            match="Notification action must include template_id",
        ):
            validate_action_config([{"type": "notification"}])

    def test_action_config_notification_with_template_id(self):
        """Accept notification action with template_id."""
        # Should not raise
        validate_action_config([{"type": "notification", "template_id": 5}])

    def test_action_config_notification_with_cooldown_and_template(self):
        """Accept notification with both cooldown_minutes and template_id."""
        # Should not raise
        validate_action_config(
            [{"type": "notification", "template_id": 5, "cooldown_minutes": 60}]
        )

    def test_action_config_stop_machine_without_machine_id(self):
        """Reject stop_machine action without machine_id."""
        with pytest.raises(
            DjangoValidationError,
            match="stop_machine action must include machine_id",
        ):
            validate_action_config([{"type": "stop_machine"}])

    def test_action_config_stop_machine_with_machine_id(self):
        """Accept stop_machine action with machine_id."""
        # Should not raise
        validate_action_config([{"type": "stop_machine", "machine_id": "M-123"}])

    def test_action_config_stop_machine_with_cooldown(self):
        """Accept stop_machine with cooldown_minutes."""
        # Should not raise
        validate_action_config(
            [
                {
                    "type": "stop_machine",
                    "machine_id": "M-456",
                    "cooldown_minutes": 120,
                }
            ]
        )

    def test_action_config_multiple_actions_mixed(self):
        """Accept multiple actions with mixed types."""
        # Should not raise
        validate_action_config(
            [
                {"type": "notification", "template_id": 5, "cooldown_minutes": 60},
                {"type": "stop_machine", "machine_id": "M-123"},
            ]
        )

    def test_action_config_cooldown_none(self):
        """Accept None cooldown_minutes (optional field)."""
        # Should not raise
        validate_action_config(
            [{"type": "notification", "template_id": 5, "cooldown_minutes": None}]
        )


@pytest.mark.django_db
class TestValidateCondition:
    """Test validate_condition validator comprehensively."""

    def test_validate_condition_leaf_valid(self):
        """Accept valid leaf condition."""
        # Should not raise
        validate_condition({"type": "leaf", "operator": "gt", "threshold": 25.0})

    def test_validate_condition_leaf_with_window(self):
        """Accept leaf condition with window settings."""
        # Should not raise
        validate_condition(
            {
                "type": "leaf",
                "operator": "gt",
                "threshold": 25.0,
                "occurrences": 3,
                "window_seconds": 60,
            }
        )

    def test_validate_condition_and_valid(self):
        """Accept valid AND condition."""
        # Should not raise
        validate_condition(
            {
                "type": "and",
                "conditions": [
                    {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    {"type": "leaf", "operator": "lt", "threshold": 30.0},
                ],
            }
        )

    def test_validate_condition_or_valid(self):
        """Accept valid OR condition."""
        # Should not raise
        validate_condition(
            {
                "type": "or",
                "conditions": [
                    {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    {"type": "leaf", "operator": "lt", "threshold": 15.0},
                ],
            }
        )

    def test_validate_condition_nested_valid(self):
        """Accept valid nested condition structure."""
        # Should not raise
        validate_condition(
            {
                "type": "and",
                "conditions": [
                    {"type": "leaf", "operator": "gt", "threshold": 25.0},
                    {
                        "type": "or",
                        "conditions": [
                            {"type": "leaf", "operator": "lt", "threshold": 10.0},
                            {"type": "leaf", "operator": "eq", "threshold": 20.0},
                        ],
                    },
                ],
            }
        )

    def test_validate_condition_leaf_missing_operator(self):
        """Reject leaf condition missing operator."""
        with pytest.raises(DjangoValidationError):
            validate_condition({"type": "leaf", "threshold": 25.0})

    def test_validate_condition_leaf_missing_threshold(self):
        """Reject leaf condition missing threshold."""
        with pytest.raises(DjangoValidationError):
            validate_condition({"type": "leaf", "operator": "gt"})

    def test_validate_condition_and_missing_conditions(self):
        """Reject AND condition missing conditions."""
        with pytest.raises(DjangoValidationError):
            validate_condition({"type": "and"})

    def test_validate_condition_or_empty_conditions(self):
        """Reject OR condition with empty conditions list."""
        with pytest.raises(DjangoValidationError):
            validate_condition({"type": "or", "conditions": []})

    def test_validate_condition_invalid_operator(self):
        """Reject leaf with invalid operator."""
        with pytest.raises(DjangoValidationError):
            validate_condition(
                {"type": "leaf", "operator": "invalid_op", "threshold": 25.0}
            )

    def test_validate_condition_leaf_has_conditions(self):
        """Reject leaf node that has conditions field."""
        with pytest.raises(DjangoValidationError):
            validate_condition(
                {
                    "type": "leaf",
                    "operator": "gt",
                    "threshold": 25.0,
                    "conditions": [
                        {"type": "leaf", "operator": "lt", "threshold": 30.0}
                    ],
                }
            )


@pytest.mark.django_db
class TestRuleModel:
    """Test Rule model creation and methods."""

    def setup_method(self):
        """Setup test fixtures."""
        self.device_type = DeviceType.objects.create(
            name="Temperature Sensor", metric_unit="°C"
        )
        self.device = Device.objects.create(
            name="Test Device",
            serial_number="TEST-001",
            device_type=self.device_type,
        )

    def test_rule_str_method(self):
        """Test Rule __str__ representation."""
        rule = Rule.objects.create(
            device=self.device,
            name="High Temperature Alert",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        expected_str = "High Temperature Alert - Test Device"
        assert str(rule) == expected_str

    def test_rule_str_with_special_characters(self):
        """Test Rule __str__ with special characters in names."""
        rule = Rule.objects.create(
            device=self.device,
            name="Alert: Temperature >25°C",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        assert str(rule) == "Alert: Temperature >25°C - Test Device"

    def test_rule_with_long_names(self):
        """Test Rule __str__ with long names."""
        rule = Rule.objects.create(
            device=self.device,
            name=("This is a very long rule name that tests string " "representation"),
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        assert "This is a very long rule name" in str(rule)

    def test_rule_creation_with_defaults(self):
        """Test Rule creation with default values."""
        rule = Rule.objects.create(
            device=self.device,
            name="Default Rule",
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        assert rule.is_enabled is True
        assert rule.description is None
        assert rule.last_triggered_at is None
        assert rule.event_cooldown_until is None

    def test_rule_with_description(self):
        """Test Rule with description field."""
        rule = Rule.objects.create(
            device=self.device,
            name="Rule with Description",
            description=("This rule triggers when temperature exceeds 25°C"),
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        assert rule.description == ("This rule triggers when temperature exceeds 25°C")

    def test_rule_disabled(self):
        """Test Rule with is_enabled=False."""
        rule = Rule.objects.create(
            device=self.device,
            name="Disabled Rule",
            is_enabled=False,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        assert rule.is_enabled is False

    def test_rule_with_complex_condition(self):
        """Test Rule with complex nested condition."""
        condition = {
            "type": "and",
            "conditions": [
                {"type": "leaf", "operator": "gt", "threshold": 25.0},
                {
                    "type": "or",
                    "conditions": [
                        {"type": "leaf", "operator": "lt", "threshold": 10.0},
                        {"type": "leaf", "operator": "eq", "threshold": 20.0},
                    ],
                },
            ],
        }

        rule = Rule.objects.create(
            device=self.device,
            name="Complex Rule",
            is_enabled=True,
            condition=condition,
            action_config=[],
        )

        assert rule.condition["type"] == "and"
        assert len(rule.condition["conditions"]) == 2

    def test_rule_with_action_config_notification(self):
        """Test Rule with notification action config."""
        action_config = [
            {
                "type": "notification",
                "template_id": 5,
                "cooldown_minutes": 60,
            }
        ]

        rule = Rule.objects.create(
            device=self.device,
            name="Rule with Notification",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=action_config,
        )

        assert rule.action_config[0]["type"] == "notification"
        assert rule.action_config[0]["template_id"] == 5

    def test_rule_with_action_config_stop_machine(self):
        """Test Rule with stop_machine action config."""
        action_config = [
            {
                "type": "stop_machine",
                "machine_id": "M-123",
                "cooldown_minutes": 120,
            }
        ]

        rule = Rule.objects.create(
            device=self.device,
            name="Rule with Stop Machine",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=action_config,
        )

        assert rule.action_config[0]["type"] == "stop_machine"
        assert rule.action_config[0]["machine_id"] == "M-123"

    def test_rule_with_multiple_actions(self):
        """Test Rule with multiple action configs."""
        action_config = [
            {
                "type": "notification",
                "template_id": 5,
                "cooldown_minutes": 60,
            },
            {
                "type": "stop_machine",
                "machine_id": "M-123",
                "cooldown_minutes": 120,
            },
        ]

        rule = Rule.objects.create(
            device=self.device,
            name="Rule with Multiple Actions",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=action_config,
        )

        assert len(rule.action_config) == 2
        assert rule.action_config[0]["type"] == "notification"
        assert rule.action_config[1]["type"] == "stop_machine"

    def test_rule_cascade_delete_with_events(self):
        """Test Rule can be deleted with associated events."""
        from apps.events.models import Event

        rule = Rule.objects.create(
            device=self.device,
            name="Rule for Cascade",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        event = Event.objects.create(
            rule=rule,
            severity=Event.EventSeverity.WARNING,
            message="Test event",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        event_id = event.id
        rule_id = rule.id

        assert Rule.objects.filter(id=rule_id).exists()
        assert Event.objects.filter(id=event_id).exists()

        rule.delete()

        assert not Rule.objects.filter(id=rule_id).exists()
        assert not Event.objects.filter(id=event_id).exists()

    def test_rule_ordering_by_created_at_descending(self):
        """Test Rule queryset is ordered by created_at descending."""
        rule1 = Rule.objects.create(
            device=self.device,
            name="First Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        rule2 = Rule.objects.create(
            device=self.device,
            name="Second Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 30.0},
            action_config=[],
        )

        rules = list(Rule.objects.all())
        assert rules[0].id == rule2.id
        assert rules[1].id == rule1.id
