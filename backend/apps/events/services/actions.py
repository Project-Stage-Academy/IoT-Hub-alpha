"""Action dispatch for triggered rules (notifications, machine control)."""

import logging

from apps.rules.services.data_structure import ActionConfig

logger = logging.getLogger("apps.rules")


def action_dispatch(action_config: ActionConfig, rule, aggregate) -> None:
    """
    Dispatch action based on action config type.

    Routes to appropriate handler (notification, stop_machine, etc) based on
    action_config.type. Handles errors gracefully to prevent failure of
    one action from blocking other actions.

    Args:
        action_config: ActionConfig with type and template_id
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Returns:
        None - fires actions asynchronously
    """
    try:
        if action_config.type == "notification":
            dispatch_msg(action_config, rule, aggregate)
        elif action_config.type == "stop_machine":
            stop_machine(action_config, rule, aggregate)
        else:
            logger.warning(
                f"Unknown action type: {action_config.type}",
                extra={
                    "rule_id": str(rule.id),
                    "action_type": action_config.type,
                },
            )
    except Exception as e:
        logger.error(
            f"Error dispatching action {action_config.type}: {e}",
            exc_info=True,
            extra={
                "rule_id": str(rule.id),
                "action_type": action_config.type,
            },
        )


def dispatch_msg(action_config: ActionConfig, rule, aggregate) -> None:
    """
    Dispatch notification message (email, SMS, Slack, etc).

    Validates notification template exists and logs the dispatch action.
    Placeholder for future integration with notification delivery system.

    Args:
        action_config: ActionConfig with notification template ID
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Side Effects:
        - Validates NotificationTemplate exists
        - Logs notification dispatch action
    """
    from apps.notifications.models import NotificationTemplate

    try:
        template_id = action_config.template_id
        template = NotificationTemplate.objects.get(id=template_id)

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
        action_config: ActionConfig with type=stop_machine
        rule: Rule object that was triggered
        aggregate: EvalResults with telemetry snapshot

    Side Effects:
        - Logs stop machine action (actual control stub)
    """
    logger.info(
        "Stop machine action triggered (stub)",
        extra={
            "rule_id": str(rule.id),
        },
    )
