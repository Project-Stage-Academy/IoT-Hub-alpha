import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create admin superuser and groups with permissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-superuser",
            action="store_true",
            help="Skip superuser creation",
        )
        parser.add_argument(
            "--skip-groups",
            action="store_true",
            help="Skip groups creation",
        )
        parser.add_argument(
            "--skip-users",
            action="store_true",
            help="Skip users creation",
        )

    def handle(self, *args, **options):
        if not options["skip_superuser"]:
            self.create_superuser()

        if not options["skip_groups"]:
            self.create_groups()

        if not options["skip_users"]:
            self.create_users()

        self.stdout.write(self.style.SUCCESS("\nSetup completed!"))

    def create_superuser(self):
        """Create admin superuser"""
        self.stdout.write("\nCreating superuser...")

        username = os.getenv("ADMIN_USERNAME", "admin")
        email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        password = os.getenv("ADMIN_PASSWORD", "admin123")

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'Superuser "{username}" already exists, skipping...'
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created superuser: {username}"))
        self.stdout.write(f"Email: {email}")

    def create_groups(self):
        """Create groups with permissions"""
        self.stdout.write("\nCreating groups...")

        from apps.devices.models import Device, DeviceType
        from apps.events.models import Event
        from apps.notifications.models import Notification
        from apps.rules.models import Rule
        from apps.telemetry.models import Telemetry

        # Define permissions per model for each role
        # Admin has already all permissions
        roles_config = {
            "Operators": {
                Device: ["add", "change", "view"],
                DeviceType: ["view"],
                Event: ["change", "view"],
                Rule: ["add", "change", "view"],
                Telemetry: ["view"],
                Notification: ["view"],
            },
            "Viewers": {
                Device: ["view"],
                DeviceType: ["view"],
                Event: ["view"],
                Rule: ["view"],
                Telemetry: ["view"],
                Notification: ["view"],
            },
        }

        for role_name, model_permissions in roles_config.items():
            group, created = Group.objects.get_or_create(name=role_name)

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {role_name}"))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Group "{role_name}" already exists, updating permissions...'
                ))
                group.permissions.clear()

            for model, perm_types in model_permissions.items():
                content_type = ContentType.objects.get_for_model(model)
                for perm_type in perm_types:
                    codename = f"{perm_type}_{model._meta.model_name}"
                    try:
                        perm = Permission.objects.get(
                            codename=codename,
                            content_type=content_type,
                        )
                        group.permissions.add(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f"Permission {codename} not found"
                        ))

            perm_count = group.permissions.count()
            self.stdout.write(f"{perm_count} permissions assigned")

    def create_users(self):
        """Create operator and viewer users"""
        self.stdout.write("\nCreating users...")

        users_config = [
            {
                "username": os.getenv("OPERATOR_USERNAME", "operator"),
                "email": os.getenv("OPERATOR_EMAIL", "operator@example.com"),
                "password": os.getenv("OPERATOR_PASSWORD", "operator123"),
                "group": "Operators",
            },
            {
                "username": os.getenv("VIEWER_USERNAME", "viewer"),
                "email": os.getenv("VIEWER_EMAIL", "viewer@example.com"),
                "password": os.getenv("VIEWER_PASSWORD", "viewer123"),
                "group": "Viewers",
            },
        ]

        for user_data in users_config:
            username = user_data["username"]
            group_name = user_data["group"]

            # Check if group exists before creating users
            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Group "{group_name}" not found, skipping user "{username}"...'
                ))
                self.stdout.write(self.style.WARNING(
                    "Run without --skip-groups first"
                ))
                continue

            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(
                    f'User "{username}" already exists, skipping...'
                ))
                continue

            user = User.objects.create_user(
                username=username,
                email=user_data["email"],
                password=user_data["password"],
                is_staff=True,
            )
            user.groups.add(group)

            self.stdout.write(self.style.SUCCESS(f"Created user: {username}"))
            self.stdout.write(f"Email: {user_data['email']}")
            self.stdout.write(f"Group: {group_name}")
