"""Additional tests to improve event_handler coverage."""

import pytest
from django.utils import timezone

from apps.events.services.event_handler import get_template
from apps.notifications.models import NotificationTemplate


@pytest.mark.django_db
class TestGetTemplate:
    """Test get_template function for line 69 coverage."""

    def test_get_template_success(self):
        """get_template retrieves and returns template."""
        template = NotificationTemplate.objects.create(
            name="Test Template",
            priority=1,
            message_template="Test message",
            recipients=[{"type": "email", "address": "test@test.com"}],
        )

        result = get_template(template.id)

        assert result.id == template.id
        assert result.name == "Test Template"

    def test_get_template_returns_object(self):
        """get_template returns NotificationTemplate object."""
        template = NotificationTemplate.objects.create(
            name="Alert",
            priority=2,
            message_template="Alert: {value}",
            recipients=[{"type": "sms", "target": "+1234567890"}],
        )

        result = get_template(template.id)

        assert isinstance(result, NotificationTemplate)
        assert result.priority == 2