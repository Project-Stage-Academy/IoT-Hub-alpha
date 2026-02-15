import pytest
from django.core.exceptions import ValidationError

from apps.notifications.models import NotificationTemplate, NotificationDelivery


@pytest.mark.django_db
def test_notification_template_str():
    template = NotificationTemplate.objects.create(
        name="Alert Template",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )

    assert str(template) == "Alert Template (Priority: 1)"


@pytest.mark.django_db
def test_notification_template_recipients_requires_list():
    template = NotificationTemplate(
        name="Bad Template",
        message_template="Alert {message}",
        recipients="not-a-list",
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )

    with pytest.raises(ValidationError):
        template.full_clean()


@pytest.mark.django_db
def test_notification_template_recipients_requires_type():
    template = NotificationTemplate(
        name="Bad Template",
        message_template="Alert {message}",
        recipients=[{"address": "alerts@example.com"}],
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )

    with pytest.raises(ValidationError):
        template.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "recipients",
    [
        [],
        [{"type": "email"}],
        [{"type": "sms"}],
        [{"type": "webhook"}],
        [{"type": "pager", "address": "alerts@example.com"}],
    ],
)
def test_notification_template_recipients_validation_errors(recipients):
    template = NotificationTemplate(
        name="Bad Template",
        message_template="Alert {message}",
        recipients=recipients,
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )

    with pytest.raises(ValidationError):
        template.full_clean()


@pytest.mark.django_db
def test_notification_delivery_defaults_and_str(event):
    template = NotificationTemplate.objects.create(
        name="Delivery Template",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )

    delivery = NotificationDelivery.objects.create(
        event=event,
        template=template,
        notification_type=NotificationDelivery.NotificationType.EMAIL,
        recipient_address="alerts@example.com",
        rendered_message="Alert Warning: Something happened",
    )

    assert delivery.status == NotificationDelivery.NotificationStatus.PENDING
    assert "Delivery" in str(delivery)


@pytest.mark.django_db
def test_notification_delivery_deleted_when_event_deleted(event):
    template = NotificationTemplate.objects.create(
        name="Cascade Template",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )
    NotificationDelivery.objects.create(
        event=event,
        template=template,
        notification_type=NotificationDelivery.NotificationType.EMAIL,
        recipient_address="alerts@example.com",
        rendered_message="Alert Warning: Something happened",
    )

    event.delete()

    assert NotificationDelivery.objects.count() == 0
