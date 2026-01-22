# Django Admin - Roles and Permissions

## Overview

The IoT Hub admin interface uses Django's built-in permission system with three roles:

| Role | Description | User Type |
|------|-------------|-----------|
| Admin | Full access to all resources | Superuser |
| Operators | Can manage devices, rules, and acknowledge events | Staff |
| Viewers | Read-only access to all resources | Staff |

## Permissions Map

### Admin (Superuser)

Superusers bypass all permission checks and have full access to:
- All CRUD operations on all models
- User and group management
- Django Admin configuration

### Operators

| Model | Add | Change | Delete | View |
|-------|-----|--------|--------|------|
| Device | Yes | Yes | No | Yes |
| DeviceType | No | No | No | Yes |
| Event | No | Yes | No | Yes |
| Rule | Yes | Yes | No | Yes |
| Telemetry | No | No | No | Yes |
| Notification | No | No | No | Yes |

**Capabilities:**
- Register and configure devices
- Create and modify alerting rules
- Acknowledge and resolve events
- View telemetry data and notifications

### Viewers

| Model | Add | Change | Delete | View |
|-------|-----|--------|--------|------|
| Device | No | No | No | Yes |
| DeviceType | No | No | No | Yes |
| Event | No | No | No | Yes |
| Rule | No | No | No | Yes |
| Telemetry | No | No | No | Yes |
| Notification | No | No | No | Yes |

**Capabilities:**
- View all data (read-only)
- Monitor dashboards
- No modification permissions


## Environment Variables

Configure user credentials in `.env`:

```env
# Admin (superuser)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin123

# Operator
OPERATOR_USERNAME=operator
OPERATOR_EMAIL=operator@example.com
OPERATOR_PASSWORD=operator123

# Viewer
VIEWER_USERNAME=viewer
VIEWER_EMAIL=viewer@example.com
VIEWER_PASSWORD=viewer123
```

## Setup Command

Initialize roles and users with the management command:

```bash
# Full setup: superuser + groups + users
python manage.py setup_roles

# Skip specific steps
python manage.py setup_roles --skip-superuser
python manage.py setup_roles --skip-groups
python manage.py setup_roles --skip-users
```

## Access Django Admin

After setup, access the admin interface at:

```
http://localhost:8000/admin/
```

Login with the appropriate credentials based on the role needed.
