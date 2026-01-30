from pydantic import UUID4
from .data_structure import AggregateStructure
from .actions import action_dispatch
from apps.notifications.models import NotificationTemplate

def trigger_engine(trigger_aggregation: dict[UUID4, AggregateStructure]):
    for rule_id, aggregate in trigger_aggregation.items():
        rule = aggregate['rule']
        
        for action_config in rule.action_config:
            action_dispatch(action_config, rule, aggregate)