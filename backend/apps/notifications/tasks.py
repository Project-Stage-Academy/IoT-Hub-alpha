from celery import shared_task
from datetime import datetime
from apps.notifications.models import NotificationDelivery
from apps.rules.services.senders import NotificationSender, SendFailed  # wherever you put it
from apps.rules.services.data_structure import NormalizedRecipient
from apps.events.models import Event
from apps.notifications.models import NotificationTemplate


@shared_task(bind=True, max_retries=5)
def send_notification_with_retries(self, notif: dict[str, str], msg: str, template_id, event_id) -> None:
    event = Event.objects.get(id=event_id)
    template = NotificationTemplate.objects.get(id=template_id)
    sender = NotificationSender(notif=notif, msg=msg)
    send_status: bool = True

    try:
        sender.send_once()
        return

    except SendFailed as exc:
        send_status = False
        delay_minutes = 5
        raise self.retry(exc=exc, countdown=delay_minutes * 60)

    except Exception as exc:
        send_status = False
        raise
    
    finally:
        record_notification(notif, msg, event, template, send_status, self.request.retries, exc)

def record_notification(notif, msg, event, template, send_status, count, error = None):
    notif_clean = NormalizedRecipient.model_validate(notif)
    notif_deliv = NotificationDelivery(
        notification_type = notif_clean.type,
        recipient_address = notif_clean.target,
        recipient_name = notif_clean.name,
        status = send_status,
        attempt_count = count,
        error_message = error,
        rendered_message = msg,
        sent_at = datetime.now(),
        event = event,
        template = template
        )
    
    print(f" Notf_deliv: {notif_deliv}")