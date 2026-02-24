import logging
from uuid import UUID
from .data_structure import EvalResults
from apps.rules.models import Rule

logger = logging.getLogger("apps.rules")


def trigger_engine_realtime(
    rule_id: UUID, device_id: UUID, eval_result: EvalResults, producer
) -> None:
    """
    Real-time version: send event to Kafka (no DB writes).

    Event creation and action dispatch will be handled asynchronously
    by EventConsumer reading from the events topic.

    Args:
        rule_id: ID of triggered rule
        device_id: ID of device that triggered rule
        eval_result: Evaluation results (trigger, values, timestamps)
        producer: Kafka producer to send events
    """
    try:
        rule = Rule.objects.get(id=rule_id)
    except Rule.DoesNotExist:
        logger.error(
            "Rule not found",
            extra={"rule_id": str(rule_id), "device_id": str(device_id)},
        )
        return

    event_timestamp = None
    if eval_result.start:
        event_timestamp = eval_result.start.isoformat()
    elif eval_result.end:
        event_timestamp = eval_result.end.isoformat()

    event_message = {
        "type": "internal",
        "rule_id": str(rule_id),
        "device_id": str(device_id),
        "timestamp": event_timestamp,
        "severity": "warning",  # Default severity, can be overridden by EventConsumer
        "message": f"Rule '{rule.name}' triggered",
        "execution_results": [],
        "telemetry_snapshot": eval_result.to_dict(),
    }

    try:
        producer.send("events", event_message)
        logger.info(
            "Event published to Kafka",
            extra={
                "rule_id": str(rule_id),
                "device_id": str(device_id),
                "message": event_message.get("message"),
            },
        )
    except Exception as e:
        logger.error(
            "Failed to publish event to Kafka",
            extra={
                "rule_id": str(rule_id),
                "device_id": str(device_id),
                "error": str(e),
            },
            exc_info=True,
        )
