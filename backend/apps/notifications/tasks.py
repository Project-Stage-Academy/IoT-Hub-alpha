import json
import logging
import urllib.request
from typing import Any, Iterable

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from apps.events.models import Event
from .models import NotificationDelivery

logger = logging.getLogger("apps.notifications")

WEBHOOKS_ENABLED = settings.WEBHOOKS_ENABLED
WEBHOOK_TIMEOUT_SECONDS = settings.WEBHOOK_TIMEOUT_SECONDS


def enqueue_notification_deliveries(
    *,
    event: Any,
    template: Any,
    recipients: Iterable[Any],
    rendered_message: str,
) -> list[NotificationDelivery]:
    deliveries: list[NotificationDelivery] = []
    for recipient in recipients:
        delivery = NotificationDelivery.objects.create(
            event=event,
            template=template,
            notification_type=recipient.type,
            recipient_address=recipient.target,
            recipient_name=recipient.name,
            rendered_message=rendered_message,
        )
        deliveries.append(delivery)

    for delivery in deliveries:
        try:
            process_notification_delivery.delay(delivery.id)
        except Exception as exc:  # noqa: BLE001 - best effort enqueue
            logger.warning(
                "notifications.delivery.enqueue_failed",
                extra={"delivery_id": delivery.id, "error": str(exc)},
            )

    return deliveries


def _build_webhook_payload(delivery: NotificationDelivery) -> dict[str, Any]:
    event = delivery.event
    rule = event.rule
    device_id = str(rule.device_id)
    return {
        "event_id": event.id,
        "rule_id": str(event.rule_id),
        "device_id": device_id,
        "severity": event.severity,
        "message": event.message,
        "status": event.status,
        "timestamp": event.timestamp.isoformat(),
        "execution_results": event.execution_results,
        "telemetry_snapshot": event.telemetry_snapshot,
    }


def _post_webhook(url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Webhook responded with HTTP {resp.status}")


def _update_execution_results(delivery: NotificationDelivery) -> None:
    """
    Sync Event.execution_results with delivery status counts for a template.
    """
    event_id = delivery.event_id
    template_id = delivery.template_id

    with transaction.atomic():
        event = Event.objects.select_for_update().get(id=event_id)
        qs = NotificationDelivery.objects.filter(
            event_id=event_id, template_id=template_id
        )
        counts = {
            row["status"]: row["count"]
            for row in qs.values("status").annotate(count=Count("id"))
        }
        sent_count = counts.get(NotificationDelivery.NotificationStatus.SENT, 0)
        failed_count = counts.get(NotificationDelivery.NotificationStatus.FAILED, 0)
        pending_count = counts.get(NotificationDelivery.NotificationStatus.PENDING, 0)
        total = sent_count + failed_count + pending_count
        last_attempt_at = qs.aggregate(last=Max("last_attempt_at")).get("last")

        if pending_count > 0:
            status = "queued"
        elif failed_count > 0:
            status = "failed"
        else:
            status = "sent"

        results_raw = event.execution_results or []
        results = results_raw if isinstance(results_raw, list) else []
        updated = False

        for item in results:
            if (
                item.get("type") == "notification"
                and str(item.get("template_id")) == str(template_id)
            ):
                item.update(
                    {
                        "status": status,
                        "recipient_count": total or item.get("recipient_count"),
                        "sent_count": sent_count,
                        "failed_count": failed_count,
                        "pending_count": pending_count,
                        "last_attempt_at": (
                            last_attempt_at.isoformat() if last_attempt_at else None
                        ),
                    }
                )
                if pending_count == 0 and last_attempt_at:
                    item["completed_at"] = last_attempt_at.isoformat()
                updated = True
                break

        if not updated:
            results.append(
                {
                    "type": "notification",
                    "template_id": template_id,
                    "status": status,
                    "recipient_count": total,
                    "sent_count": sent_count,
                    "failed_count": failed_count,
                    "pending_count": pending_count,
                    "last_attempt_at": (
                        last_attempt_at.isoformat() if last_attempt_at else None
                    ),
                    "completed_at": (
                        last_attempt_at.isoformat()
                        if pending_count == 0 and last_attempt_at
                        else None
                    ),
                }
            )

        event.execution_results = results
        event.save(update_fields=["execution_results"])


@shared_task(bind=True, name="apps.notifications.tasks.process_delivery", max_retries=10)
def process_notification_delivery(self, delivery_id: int) -> None:
    try:
        delivery = NotificationDelivery.objects.select_related(
            "event",
            "template",
            "event__rule",
            "event__rule__device",
        ).get(id=delivery_id)
    except NotificationDelivery.DoesNotExist:
        logger.warning("notifications.delivery.missing", extra={"delivery_id": delivery_id})
        return

    now = timezone.now()
    delivery.attempt_count += 1
    delivery.last_attempt_at = now
    delivery.save(update_fields=["attempt_count", "last_attempt_at"])

    if delivery.notification_type == NotificationDelivery.NotificationType.WEBHOOK:
        if not WEBHOOKS_ENABLED:
            delivery.status = NotificationDelivery.NotificationStatus.FAILED
            delivery.error_message = "Webhooks disabled by configuration"
            delivery.save(update_fields=["status", "error_message"])
            _update_execution_results(delivery)
            logger.info(
                "notifications.webhook.skipped",
                extra={"delivery_id": delivery.id, "reason": "disabled"},
            )
            return

        try:
            _post_webhook(delivery.recipient_address, _build_webhook_payload(delivery))
        except Exception as exc:  # noqa: BLE001 - want retry on any transport error
            delivery.error_message = str(exc)
            delivery.status = NotificationDelivery.NotificationStatus.PENDING
            delivery.save(update_fields=["status", "error_message"])
            _update_execution_results(delivery)

            max_retries = max(1, delivery.template.retry_count)
            if self.request.retries >= max_retries:
                delivery.status = NotificationDelivery.NotificationStatus.FAILED
                delivery.save(update_fields=["status"])
                _update_execution_results(delivery)
                logger.warning(
                    "notifications.webhook.failed",
                    extra={"delivery_id": delivery.id, "error": str(exc)},
                )
                return

            delay = max(1, delivery.template.retry_delay_minutes) * 60
            delay *= 2 ** self.request.retries
            raise self.retry(exc=exc, countdown=delay)

        delivery.status = NotificationDelivery.NotificationStatus.SENT
        delivery.sent_at = now
        delivery.error_message = None
        delivery.save(update_fields=["status", "sent_at", "error_message"])
        _update_execution_results(delivery)
        logger.info("notifications.webhook.sent", extra={"delivery_id": delivery.id})
        return

    # Email/SMS stubs: record as sent without external calls.
    delivery.status = NotificationDelivery.NotificationStatus.SENT
    delivery.sent_at = now
    delivery.error_message = None
    delivery.save(update_fields=["status", "sent_at", "error_message"])
    _update_execution_results(delivery)
    logger.info(
        "notifications.delivery.sent",
        extra={"delivery_id": delivery.id, "type": delivery.notification_type},
    )
