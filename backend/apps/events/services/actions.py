"""Action dispatch for triggered rules."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.devices.models import Device
from apps.notifications.models import NotificationTemplate
from apps.rules.services.data_structure import ActionConfig

logger = logging.getLogger("apps.rules")


def action_dispatch(action_config: ActionConfig, rule, aggregate) -> dict[str, Any]:
    """
    Dispatch a configured action and return execution trace payload.
    """
    try:
        if action_config.type in {"notification", "alert"}:
            return dispatch_msg(action_config, rule, aggregate)
        if action_config.type == "webhook":
            return dispatch_webhook(action_config, rule, aggregate)
        if action_config.type in {"command", "stop_machine"}:
            return stop_machine(action_config, rule, aggregate)

        result = {
            "type": action_config.type,
            "status": "failed",
            "error": f"Unsupported action type: {action_config.type}",
            "completed_at": timezone.now().isoformat(),
        }
        logger.warning(
            "Unknown action type",
            extra={"rule_id": str(rule.id), "action_type": action_config.type},
        )
        return result
    except Exception as exc:
        logger.error(
            "Error dispatching action",
            exc_info=True,
            extra={"rule_id": str(rule.id), "action_type": action_config.type},
        )
        return {
            "type": action_config.type,
            "status": "failed",
            "error": str(exc),
            "completed_at": timezone.now().isoformat(),
        }


def dispatch_msg(action_config: ActionConfig, rule, aggregate) -> dict[str, Any]:
    """
    Handle notification/alert action by validating template configuration.
    """
    del aggregate
    template_id = action_config.template_id
    template = NotificationTemplate.objects.get(id=template_id)
    recipient_count = len(template.recipients or [])
    result_type = "alert" if action_config.type == "alert" else "notification"

    logger.info(
        "Alert queued",
        extra={
            "rule_id": str(rule.id),
            "template_id": template_id,
            "recipient_count": recipient_count,
        },
    )
    return {
        "type": result_type,
        "template_id": template_id,
        "status": "queued",
        "recipient_count": recipient_count,
        "completed_at": timezone.now().isoformat(),
    }


def dispatch_webhook(action_config: ActionConfig, rule, aggregate) -> dict[str, Any]:
    """
    Execute webhook callback for triggered rule.
    """
    if not settings.WEBHOOKS_ENABLED:
        raise RuntimeError("Webhooks are disabled by configuration")

    url = action_config.url
    method = action_config.method
    headers = {"Content-Type": "application/json", **(action_config.headers or {})}

    body = {
        "event_type": "rule_triggered",
        "rule_id": str(rule.id),
        "device_id": str(rule.device_id),
        "rule_name": rule.name,
        "triggered_at": timezone.now().isoformat(),
        "telemetry_snapshot": aggregate.to_dict(),
        "payload": action_config.payload or {},
    }

    request = urllib.request.Request(
        url=url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(
        request,
        timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
    ) as resp:
        status_code = int(resp.status)

    if status_code >= 400:
        raise RuntimeError(f"Webhook responded with HTTP {status_code}")

    logger.info(
        "Webhook action completed",
        extra={"rule_id": str(rule.id), "url": url, "status_code": status_code},
    )
    return {
        "type": "webhook",
        "url": url,
        "method": method,
        "status": "completed",
        "status_code": status_code,
        "completed_at": timezone.now().isoformat(),
    }


def stop_machine(action_config: ActionConfig, rule, aggregate) -> dict[str, Any]:
    """
    Execute command-like actions that modify device state.
    """
    del aggregate
    if action_config.type == "stop_machine":
        command = "stop_machine"
        params = {"status": Device.DeviceStatus.INACTIVE}
    else:
        command = action_config.command
        params = action_config.params or {}

    if command == "stop_machine":
        new_status = Device.DeviceStatus.INACTIVE
    elif command == "set_device_status":
        new_status = params.get("status")
    else:
        raise ValueError(f"Unsupported command action: {command}")

    allowed_statuses = {choice for choice, _ in Device.DeviceStatus.choices}
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Invalid device status '{new_status}'. Allowed values: "
            f"{', '.join(sorted(allowed_statuses))}"
        )

    previous_status = rule.device.status
    if previous_status != new_status:
        rule.device.status = new_status
        rule.device.save(update_fields=["status", "updated_at"])

    logger.info(
        "Device command action completed",
        extra={
            "rule_id": str(rule.id),
            "device_id": str(rule.device_id),
            "command": command,
            "previous_status": previous_status,
            "new_status": new_status,
        },
    )
    result = {
        "type": "command" if action_config.type == "command" else "stop_machine",
        "command": command,
        "status": "completed",
        "device_id": str(rule.device_id),
        "previous_status": previous_status,
        "new_status": new_status,
        "completed_at": timezone.now().isoformat(),
    }
    if action_config.type == "stop_machine":
        result["machine_id"] = action_config.machine_id
    elif action_config.machine_id:
        result["machine_id"] = action_config.machine_id
    return result
