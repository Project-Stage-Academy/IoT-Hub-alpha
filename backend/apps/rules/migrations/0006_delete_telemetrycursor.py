# Generated migration to delete TelemetryCursor model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("rules", "0005_remove_rule_comparison_operator_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TelemetryCursor",
        ),
    ]