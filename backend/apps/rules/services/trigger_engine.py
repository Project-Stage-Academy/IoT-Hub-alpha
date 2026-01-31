from uuid import UUID
from .data_structure import AggregateStructure, ActionConfig
from .actions import action_dispatch
from apps.rules.models import Rule


def trigger_engine(trigger_aggregation: dict[UUID, AggregateStructure]) -> None:
    """
    Dispatch action config per rules

    :param trigger_aggregation: Description
    :type trigger_aggregation: dict[UUID4, AggregateStructure]
    """
    rules = Rule.objects.in_bulk(trigger_aggregation.keys())

    for rule_id, aggregate in trigger_aggregation.items():
        rule = rules[rule_id]

        for action_config in rule.action_config:
            action_config = ActionConfig.model_validate(action_config)
            action_dispatch(action_config, rule, aggregate)
