from uuid import UUID
from apps.events.services.external_events_data_structure import FakeRule
from apps.rules.models import Rule


def handle_rules(payload, payload_type, consumer, logger):
    if payload_type == "internal":
        rule_id = UUID(payload["rule_id"])
        device_id = UUID(payload["device_id"])

        try:
            rule = Rule.objects.get(id=rule_id)
        except Rule.DoesNotExist:
            logger.error(
                f"Rule not found: {rule_id}",
                extra={
                    "rule_id": str(rule_id),
                    "device_id": str(device_id),
                },
            )
            consumer.commit(asynchronous=False)
            return None, None, None

    else:
        rule_id = payload["rule_id"]
        device_id = payload["device_id"]
        action_config = payload["action_config"]
        rule = FakeRule.model_validate(
            {
                "id": str(rule_id),
                "action_config": action_config,
                "event_cooldown_until": payload["cooldown_min"],
            }
        )

    return rule, rule_id, device_id
