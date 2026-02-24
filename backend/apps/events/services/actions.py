"""Action dispatch for triggered rules (notifications, machine control)."""

import logging

from apps.rules.services.data_structure import ActionConfig

logger = logging.getLogger("apps.rules")


def action_dispatch(action_config: ActionConfig, rule, aggregate) -> None:
    """
    Dispatch action based on action config type.

    Routes to appropriate handler (notification, stop_machine, etc) based on
    action_config.action_type. Handles errors gracefully to prevent failure of
    one action from blocking other actions.

    Args:
        action_config: ActionConfig with action_type and action_params
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Returns:
        None - fires actions asynchronously
    """
    try:
        if action_config.action_type == "notification":
            dispatch_msg(action_config, rule, aggregate)
        elif action_config.action_type == "stop_machine":
            stop_machine(action_config, rule, aggregate)
        else:
            logger.warning(
                f"Unknown action type: {action_config.action_type}",
                extra={
                    "rule_id": str(rule.id),
                    "action_type": action_config.action_type,
                },
            )
    except Exception as e:
        logger.error(
            f"Error dispatching action {action_config.action_type}: {e}",
            exc_info=True,
            extra={
                "rule_id": str(rule.id),
                "action_type": action_config.action_type,
            },
        )


def dispatch_msg(action_config: ActionConfig, rule, aggregate) -> None:
    """
    Dispatch notification message (email, SMS, Slack, etc).

    Enqueues notification for delivery via configured channels
    (email, SMS, Slack). Uses NotificationTemplate to render message
    with rule context.

    Args:
        action_config: ActionConfig with notification template ID
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Side Effects:
        - Creates NotificationDelivery records in database
        - Enqueues async notification delivery task
    """
    from apps.notifications.models import NotificationTemplate
    from apps.notifications.services import queue_notification

    try:
        template_id = action_config.action_params.get("template_id")
        template = NotificationTemplate.objects.get(id=template_id)

        queue_notification(
            template=template,
            context={
                "rule_name": rule.name,
                "device_id": rule.device_id,
                "values": aggregate.values,
                "start": aggregate.start,
                "end": aggregate.end,
            },
        )

        logger.info(
            "Notification queued",
            extra={
                "rule_id": str(rule.id),
                "template_id": template_id,
            },
        )
    except Exception as e:
        logger.error(
            f"Error queuing notification: {e}",
            exc_info=True,
            extra={
                "rule_id": str(rule.id),
            },
        )
        raise


def stop_machine(action_config: ActionConfig, rule, aggregate) -> None:
    """
    Stop machine control action (stub).

    Placeholder for future machine control integration. Currently logs
    the action but does not actually send control signal.

    Args:
        action_config: ActionConfig with machine ID
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Side Effects:
        - Logs stop machine action (actual control stub)
    """
    machine_id = action_config.action_params.get("machine_id")

    logger.info(
        "Stop machine action triggered (stub)",
        extra={
            "rule_id": str(rule.id),
            "machine_id": machine_id,
        },
    )
