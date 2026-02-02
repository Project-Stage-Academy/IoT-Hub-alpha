import pytest
import logging
from uuid import uuid4
from unittest.mock import patch, Mock
from pydantic import ValidationError
from apps.rules.services.data_structure import EvalResults
from apps.rules.services.trigger_engine import trigger_engine


def test_trigger_engine_no_triggers_does_nothing():
    """
    Tests trigger engine does nothing with no triggers provided
    """
    with patch("apps.rules.services.trigger_engine.Rule.objects.in_bulk", return_value={}) as mock_in_bulk, \
         patch("apps.rules.services.trigger_engine.action_dispatch") as mock_dispatch:
        trigger_engine({})

    mock_in_bulk.assert_not_called()
    mock_dispatch.assert_not_called()


def test_trigger_engine_dispatches_each_action_config_for_each_triggered_rule():
    """
    Checks if each triggered rule dispatches an action config
    """
    rule_id = uuid4()
    aggregate = EvalResults(trigger=True, values=[123.0])

    fake_rule = Mock()
    fake_rule.action_config = [
        {"type": "notification", "template_id": 1},
        {"type": "stop_machine"},
    ]

    with patch("apps.rules.services.trigger_engine.Rule.objects.in_bulk", return_value={rule_id: fake_rule}) as mock_in_bulk, \
         patch("apps.rules.services.trigger_engine.action_dispatch") as mock_dispatch:
        trigger_engine({rule_id: aggregate})

    mock_in_bulk.assert_called_once_with({rule_id})
    assert mock_dispatch.call_count == 2


def test_trigger_engine_multiple_rules_calls_dispatch_for_each_rule():
    """
    Tests multiple dispatch calls for a multiple rules
    """
    rule_id_1 = uuid4()
    rule_id_2 = uuid4()

    agg1 = EvalResults(trigger=True, values=[1.0])
    agg2 = EvalResults(trigger=True, values=[2.0])

    rule1 = Mock()
    rule1.action_config = [{"type": "stop_machine"}]

    rule2 = Mock()
    rule2.action_config = [{"type": "notification", "template_id": 1}]

    with patch(
        "apps.rules.services.trigger_engine.Rule.objects.in_bulk",
        return_value={rule_id_1: rule1, rule_id_2: rule2},
    ) as mock_in_bulk, patch(
        "apps.rules.services.trigger_engine.action_dispatch"
    ) as mock_dispatch:
        trigger_engine({rule_id_1: agg1, rule_id_2: agg2})

    mock_in_bulk.assert_called_once()
    assert mock_dispatch.call_count == 2


def test_trigger_engine_logs_warning_and_returns_on_malformed_action_config():
    """
    Check that malformed config causes the program to log the error and skip the entry
    """
    rule_id = uuid4()
    agg = EvalResults(trigger=True, values=[1.0])

    fake_rule = Mock()
    fake_rule.id = rule_id
    fake_rule.action_config = [{"type": "nope"}]

    with patch(
        "apps.rules.services.trigger_engine.Rule.objects.in_bulk",
        return_value={rule_id: fake_rule},
    ), patch(
        "apps.rules.services.trigger_engine.action_dispatch"
    ) as mock_dispatch, patch.object(
        logging, "warning"
    ) as mock_warning:
        ret = trigger_engine({rule_id: agg})

    assert ret is None

    mock_dispatch.assert_not_called()

    mock_warning.assert_called_once()
    args, kwargs = mock_warning.call_args

    assert args[0] == "Malformed config!"
    assert "extra" in kwargs
    assert "event" in kwargs["extra"]
    assert "error" in kwargs["extra"]["event"]

    err = kwargs["extra"]["event"]["error"]
    assert f"Malformed config detected at: {fake_rule.id}" in err


def test_trigger_engine_missing_rule_id_in_bulk_logs_warning():
    """
    Missing rule ID in DB but aggregate present should return and log warning
    """
    rule_id = uuid4()
    aggregate = EvalResults(trigger=True, values=[123.0])

    with patch(
        "apps.rules.services.trigger_engine.Rule.objects.in_bulk",
        return_value={},
    ), patch(
        "apps.rules.services.trigger_engine.action_dispatch"
    ) as mock_dispatch, patch.object(
        logging, "warning"
    ) as mock_warning:
        trigger_engine({rule_id: aggregate})
        
        mock_warning.assert_called_once()
        args, kwargs = mock_warning.call_args
        assert args[0] == "Rules not found for devices"
        assert "extra" in kwargs
        assert "event" in kwargs["extra"]
        assert "error" in kwargs["extra"]["event"]
        
def test_trigger_engine_empty_aggregate_logs_info():
    """
    Missing rule ID in DB but aggregate present should return and log warning
    """
    rule_id = uuid4()
    aggregate = EvalResults(trigger=True, values=[123.0])

    with patch(
        "apps.rules.services.trigger_engine.Rule.objects.in_bulk",
        return_value={},
    ), patch(
        "apps.rules.services.trigger_engine.action_dispatch"
    ) as mock_dispatch, patch.object(
        logging, "info"
    ) as mock_info:
        trigger_engine({})
        
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args
        assert args[0] == "No offending telemetry"
        assert "extra" in kwargs
        assert "event" in kwargs["extra"]
        assert "message" in kwargs["extra"]["event"]