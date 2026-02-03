import logging
from uuid import UUID
from pydantic import ValidationError
from .data_structure import ActionConfig
from .data_structure import EvalResults
from .actions import action_dispatch
from apps.rules.models import Rule

logger = logging.getLogger("apps.rules")


def trigger_engine(trigger_aggregation: dict[UUID, EvalResults]) -> None:
    """
    Dispatch action config per rules

    :param trigger_aggregation: Description
    :type trigger_aggregation: dict[UUID4, AggregateStructure]
    """
    if not trigger_aggregation:
        logging.info(
            "No offending telemetry", extra={"event": {"message": "No rules broken"}}
        )
        return

    rules = Rule.objects.in_bulk(trigger_aggregation.keys())

    if not rules:
        logging.warning(
            "Rules not found for devices",
            extra={
                "event": {
                    "error": "Rule ids did not match any known rules:"
                    f"{", ".join(map(str, trigger_aggregation.keys()))}"
                }
            },
        )
        return

    for rule_id, aggregate in trigger_aggregation.items():
        rule = rules[rule_id]

        for action_config in rule.action_config:
            try:
                action_config = ActionConfig.model_validate(action_config)
            except ValidationError as e:
                logging.warning(
                    "Malformed config!",
                    extra={
                        "event": {
                            "error": "Malformed config detected"
                            f" at: {rule.id} error: {e}"
                        }
                    },
                )
                return
            action_dispatch(action_config, rule, aggregate)
