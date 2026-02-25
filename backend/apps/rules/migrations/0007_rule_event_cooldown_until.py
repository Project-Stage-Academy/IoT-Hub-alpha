# Generated migration to add event_cooldown_until field to Rule model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rules", "0008_merge_20260225_0001"),
    ]

    operations = [
        migrations.AddField(
            model_name="rule",
            name="event_cooldown_until",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Timestamp when cooldown for event creation expires",
            ),
        ),
    ]
