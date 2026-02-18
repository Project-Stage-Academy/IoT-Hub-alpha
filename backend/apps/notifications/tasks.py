import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol

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


@dataclass
class DeliveryStatusSummary:
    status: str
    recipient_count: int
    sent_count: int
    failed_count: int
    pending_count: int
    last_attempt_at: datetime | None

    @property
    def last_attempt_iso(self) -> str | None:
        if self.last_attempt_at is None:
            return None
        return self.last_attempt_at.isoformat()

    @property
    def completed_at_iso(self) -> str | None:
        if self.pending_count > 0 or self.last_attempt_at is None:
            return None
        return self.last_attempt_at.isoformat()


class DeliveryStrategy(Protocol):
    def send(
        self,
        *,
        task: Any,
        delivery: NotificationDelivery,
        now: datetime,
    ) -> None:
        pass


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


def _aggregate_delivery_status_summary(
    *,
    event_id: int,
    template_id: int,
) -> DeliveryStatusSummary:
    qs = NotificationDelivery.objects.filter(event_id=event_id, template_id=template_id)
    counts = {
        row["status"]: row["count"]
        for row in qs.values("status").annotate(count=Count("id"))
    }
    sent_count = counts.get(NotificationDelivery.NotificationStatus.SENT, 0)
    failed_count = counts.get(NotificationDelivery.NotificationStatus.FAILED, 0)
    pending_count = counts.get(NotificationDelivery.NotificationStatus.PENDING, 0)
    recipient_count = sent_count + failed_count + pending_count
    last_attempt_at = qs.aggregate(last=Max("last_attempt_at")).get("last")

    if pending_count > 0:
        status = "queued"
    elif failed_count > 0:
        status = "failed"
    else:
        status = "sent"

    return DeliveryStatusSummary(
        status=status,
        recipient_count=recipient_count,
        sent_count=sent_count,
        failed_count=failed_count,
        pending_count=pending_count,
        last_attempt_at=last_attempt_at,
    )


def _build_notification_result(
    *,
    template_id: int,
    summary: DeliveryStatusSummary,
    existing_recipient_count: int | None = None,
    include_completed_at: bool = True,
) -> dict[str, Any]:
    recipient_count = summary.recipient_count
    if existing_recipient_count is not None:
        recipient_count = recipient_count or existing_recipient_count

    result = {
        "type": "notification",
        "template_id": template_id,
        "status": summary.status,
        "recipient_count": recipient_count,
        "sent_count": summary.sent_count,
        "failed_count": summary.failed_count,
        "pending_count": summary.pending_count,
        "last_attempt_at": summary.last_attempt_iso,
    }
    if include_completed_at:
        result["completed_at"] = summary.completed_at_iso
    return result


def _sync_notification_result(
    *,
    execution_results: list[dict[str, Any]],
    template_id: int,
    summary: DeliveryStatusSummary,
) -> list[dict[str, Any]]:
    for item in execution_results:
        if item.get("type") == "notification" and str(item.get("template_id")) == str(
            template_id
        ):
            item.update(
                _build_notification_result(
                    template_id=template_id,
                    summary=summary,
                    existing_recipient_count=item.get("recipient_count"),
                    include_completed_at=(
                        summary.pending_count == 0
                        and summary.last_attempt_at is not None
                    ),
                )
            )
            return execution_results

    execution_results.append(
        _build_notification_result(
            template_id=template_id,
            summary=summary,
        )
    )
    return execution_results


def _update_execution_results(delivery: NotificationDelivery) -> None:
    with transaction.atomic():
        event = Event.objects.select_for_update().get(id=delivery.event_id)
        summary = _aggregate_delivery_status_summary(
            event_id=delivery.event_id,
            template_id=delivery.template_id,
        )

        results_raw = event.execution_results or []
        results = results_raw if isinstance(results_raw, list) else []
        event.execution_results = _sync_notification_result(
            execution_results=results,
            template_id=delivery.template_id,
            summary=summary,
        )

        event.save(update_fields=["execution_results"])


def _mark_delivery_pending(
    delivery: NotificationDelivery,
    *,
    error_message: str,
) -> None:
    delivery.status = NotificationDelivery.NotificationStatus.PENDING
    delivery.error_message = error_message
    delivery.save(update_fields=["status", "error_message"])
    _update_execution_results(delivery)


def _mark_delivery_failed(
    delivery: NotificationDelivery,
    *,
    error_message: str | None = None,
    preserve_existing_error: bool = False,
) -> None:
    delivery.status = NotificationDelivery.NotificationStatus.FAILED
    update_fields = ["status"]

    if not preserve_existing_error:
        delivery.error_message = error_message
        update_fields.append("error_message")

    delivery.save(update_fields=update_fields)
    _update_execution_results(delivery)


def _mark_delivery_sent(delivery: NotificationDelivery, *, now: datetime) -> None:
    delivery.status = NotificationDelivery.NotificationStatus.SENT
    delivery.sent_at = now
    delivery.error_message = None
    delivery.save(update_fields=["status", "sent_at", "error_message"])
    _update_execution_results(delivery)


class WebhookDeliveryStrategy:
    def send(
        self,
        *,
        task: Any,
        delivery: NotificationDelivery,
        now: datetime,
    ) -> None:
        if not WEBHOOKS_ENABLED:
            _mark_delivery_failed(
                delivery,
                error_message="Webhooks disabled by configuration",
            )
            logger.info(
                "notifications.webhook.skipped",
                extra={"delivery_id": delivery.id, "reason": "disabled"},
            )
            return

        try:
            _post_webhook(delivery.recipient_address, _build_webhook_payload(delivery))
        except Exception as exc:  # noqa: BLE001 - want retry on any transport error
            _mark_delivery_pending(delivery, error_message=str(exc))

            max_retries = max(1, delivery.template.retry_count)
            retries = getattr(task.request, "retries", 0)
            if retries >= max_retries:
                _mark_delivery_failed(delivery, preserve_existing_error=True)
                logger.warning(
                    "notifications.webhook.failed",
                    extra={"delivery_id": delivery.id, "error": str(exc)},
                )
                return

            delay = max(1, delivery.template.retry_delay_minutes) * 60
            delay *= 2**retries
            raise task.retry(exc=exc, countdown=delay)

        _mark_delivery_sent(delivery, now=now)
        logger.info("notifications.webhook.sent", extra={"delivery_id": delivery.id})


class EmailSmsDeliveryStrategy:
    def send(
        self,
        *,
        task: Any,
        delivery: NotificationDelivery,
        now: datetime,
    ) -> None:
        del task
        _mark_delivery_sent(delivery, now=now)
        logger.info(
            "notifications.delivery.sent",
            extra={"delivery_id": delivery.id, "type": delivery.notification_type},
        )


def _get_delivery_strategy(delivery: NotificationDelivery) -> DeliveryStrategy:
    if delivery.notification_type == NotificationDelivery.NotificationType.WEBHOOK:
        return WebhookDeliveryStrategy()
    return EmailSmsDeliveryStrategy()


@shared_task(
    bind=True,
    name="apps.notifications.tasks.process_delivery",
    max_retries=10,
)
def process_notification_delivery(self, delivery_id: int) -> None:
    try:
        delivery = NotificationDelivery.objects.select_related(
            "event",
            "template",
            "event__rule",
            "event__rule__device",
        ).get(id=delivery_id)
    except NotificationDelivery.DoesNotExist:
        logger.warning(
            "notifications.delivery.missing",
            extra={"delivery_id": delivery_id},
        )
        return

    now = timezone.now()
    delivery.attempt_count += 1
    delivery.last_attempt_at = now
    delivery.save(update_fields=["attempt_count", "last_attempt_at"])

    strategy = _get_delivery_strategy(delivery)
    strategy.send(task=self, delivery=delivery, now=now)
