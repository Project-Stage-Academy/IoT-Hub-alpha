from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rules", "0007_rule_event_cooldown_until"),
    ]

    operations = [
        migrations.CreateModel(
            name="RuleAuditLog",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("rule_id", models.UUIDField(blank=True, null=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("create", "Create"),
                            ("update", "Update"),
                            ("delete", "Delete"),
                            ("enable", "Enable"),
                            ("disable", "Disable"),
                        ],
                        max_length=32,
                    ),
                ),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("actor_user_id", models.IntegerField(blank=True, null=True)),
                (
                    "actor_username",
                    models.CharField(blank=True, max_length=150, null=True),
                ),
                ("request_id", models.CharField(blank=True, max_length=128, null=True)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("signal", "Signal"),
                            ("admin_action", "Admin Action"),
                            ("api", "API"),
                            ("system", "System"),
                        ],
                        max_length=32,
                    ),
                ),
            ],
            options={
                "db_table": "rule_audit_log",
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["created_at"], name="idx_r_audit_created_at"
                    ),
                    models.Index(fields=["rule_id"], name="idx_r_audit_rule_id"),
                    models.Index(
                        fields=["action", "created_at"],
                        name="idx_r_audit_action_created",
                    ),
                ],
            },
        ),
    ]
