## 1. Overview

Rules define conditions that are evaluated against incoming telemetry data.
When a rule evaluates to `true`, an event is generated and optional actions (notifications, automations) are triggered.

Key concepts:

- Rule – declarative definition of what to evaluate
- Condition – logical expression evaluated against telemetry
- Evaluation – execution of a rule for a given telemetry window
- Event – persistent record created when a rule is triggered

## 2. Rule Model

A rule consists of:

| Field              | Type       | Description                                            |
| ------------------ | ---------- | ------------------------------------------------------ |
| id                 | UUID       | Unique rule identifier (auto-generated)                |
| name               | string     | Human-readable name (required)                         |
| description        | string     | Short human-readable description (optional)            |
| device_id          | UUID (FK)  | Device the rule applies to (required)                  |
| condition          | JSON       | Condition definition (required)                        |
| action_config      | JSON array | List of actions to execute upon rule trigger (required)|
| is_enabled         | boolean    | Whether the rule is active (default: true)             |
| last_triggered_at  | datetime   | When the rule last fired (read-only)                   |
| created_at         | datetime   | Creation timestamp (read-only)                         |
| updated_at         | datetime   | Last modification timestamp (read-only)                |

## 3. CRUD API

All rule endpoints are available at `/api/v1/rules/` and require a **Bearer token** in the `Authorization` header.

```
Authorization: Bearer <token>
```

> **Note:** Authentication is enforced at the API Gateway level. The Django backend itself does not validate the token, but clients must always include it.

### 3.1 List Rules

```http
GET /api/v1/rules/
```

Query parameters:

| Parameter   | Type   | Description                          |
| ----------- | ------ | ------------------------------------ |
| page        | int    | Page number (1-based, default: 1)    |
| page_size   | int    | Items per page (default: 10)         |
| device_id   | UUID   | Filter by device                     |
| is_enabled  | string | Filter by enabled status (true/false)|

Example:

```bash
curl http://localhost:8000/api/v1/rules/?device_id=a80031eb-189a-49d5-93ab-11bd465143e9&is_enabled=true \
  -H "Authorization: Bearer <token>"
```

Response `200`:

```json
{
  "data": [
    {
      "id": "29e31015-4733-49f3-855a-ef7f30e6c147",
      "name": "Low Vibration Alert Lathe",
      "description": "Alerts maintenance when vibration drops",
      "device_id": "a80031eb-189a-49d5-93ab-11bd465143e9",
      "condition": {"type": "leaf", "operator": "gt", "threshold": 5},
      "action_config": [{"type": "notification", "template_id": 5}],
      "is_enabled": true,
      "last_triggered_at": null,
      "created_at": "2026-01-27T20:57:00+00:00",
      "updated_at": "2026-01-27T21:10:00+00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1,
    "next_page": null,
    "prev_page": null
  }
}
```

### 3.2 Create Rule

```http
POST /api/v1/rules/
Content-Type: application/json
```

Required fields: `name`, `condition`, `action_config`, `device_id`

Example:

```bash
curl -X POST http://localhost:8000/api/v1/rules/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "a80031eb-189a-49d5-93ab-11bd465143e9",
    "name": "Unexpected Low Current Alert",
    "description": "Alerts management when current draw indicates possible machine shutdown",
    "condition": {
      "type": "leaf",
      "operator": "gt",
      "threshold": 14.1
    },
    "action_config": [
      {
        "type": "notification",
        "template_id": 2,
        "recipients": [
          {"type": "email", "address": "a@b.com"},
          {"type": "sms", "phone": "+3800000000"},
          {"type": "webhook", "url": "http://why.com"}
        ]
      }
    ],
    "is_enabled": true
  }'
```

Response `201`:

```json
{
  "data": {
    "id": "29e31015-4733-49f3-855a-ef7f30e6c147",
    "name": "Unexpected Low Current Alert",
    "description": "Alerts management when current draw indicates possible machine shutdown",
    "device_id": "a80031eb-189a-49d5-93ab-11bd465143e9",
    "condition": {"type": "leaf", "operator": "gt", "threshold": 14.1},
    "action_config": [{"type": "notification", "template_id": 2}],
    "is_enabled": true,
    "last_triggered_at": null,
    "created_at": "2026-03-03T12:00:00+00:00",
    "updated_at": "2026-03-03T12:00:00+00:00"
  }
}
```

Validation error `400`:

```json
{"errors": {"name": "This field is required.", "condition": "This field is required."}}
```

### 3.3 Get Rule by ID

```http
GET /api/v1/rules/{rule_id}/
```

Example:

```bash
curl http://localhost:8000/api/v1/rules/29e31015-4733-49f3-855a-ef7f30e6c147/ \
  -H "Authorization: Bearer <token>"
```

Response `200`: same structure as single rule in `data` wrapper.

Response `404`:

```json
{"error": "Rule not found."}
```

### 3.4 Update Rule (Partial)

```http
PATCH /api/v1/rules/{rule_id}/
Content-Type: application/json
```

All fields are optional. Only provided fields are updated.

Example:

```bash
curl -X PATCH http://localhost:8000/api/v1/rules/29e31015-4733-49f3-855a-ef7f30e6c147/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name", "is_enabled": false}'
```

Response `200`: updated rule in `data` wrapper.

### 3.5 Delete Rule

```http
DELETE /api/v1/rules/{rule_id}/
```

Example:

```bash
curl -X DELETE http://localhost:8000/api/v1/rules/29e31015-4733-49f3-855a-ef7f30e6c147/ \
  -H "Authorization: Bearer <token>"
```

Response `204`: no content.

Response `404`:

```json
{"error": "Rule not found."}
```

## 4. Condition Schemas

### 4.1 Threshold Condition

Evaluates a single telemetry value.

```json
{
  "type": "leaf",
  "operator": "gt",
  "threshold": 80
}
```

Supported operators:

| Operator | Meaning               |
| -------- | --------------------- |
| gt       | greater than          |
| gte      | greater than or equal |
| lt       | less than             |
| lte      | less than or equal    |
| eq       | equal                 |
| ne       | not equal             |

### 4.2 Rate Condition

Triggers when N events occur in a given time window.

```json
{
  "type": "leaf",
  "operator": "gt",
  "threshold": 60.5,
  "occurrences": 5,
  "window_seconds": 250
}
```

Meaning:

Trigger if telemetry value exceeds 60.5 5 times within 250 seconds

### 4.3 Composite Condition

Combine multiple conditions using logical operators.

```json
{
    "type": "or",
    "conditions": [
    {
        "type": "leaf",
        "operator": "lt",
        "threshold": 80
    },
    {
        "type": "leaf",
        "operator": "gt",
        "threshold": 60.5,
        "occurrences": 5,
        "window_seconds": 60
    }
]
}
```

Supported composite operators:

- AND
- OR

Nested (Multiple And, Or chains are also supported) example:
```json
{
    "type": "or",
    "conditions": [
        {"type": "leaf", "operator": "gt", "threshold": 5.0},
        {"type": "and",
        "conditions": [
            {"type": "leaf", "operator": "gt", "threshold": 15.0},
            {"type": "leaf", "operator": "lt", "threshold": 20.0}
            ]
        },
    ],
}
```

## 5. Enabling and Disabling Rules

Disabling a Rule

```http
PATCH /api/v1/rules/{rule_id}/
Content-Type: application/json
```
```json
{
    "is_enabled": false
}
```
Disabled rules:

- Are not evaluated
- Do not generate events
- Preserve evaluation history

Enable a Rule
```json
{
  "is_enabled": true
}
```

Once enabled, the rule will be evaluated on the next telemetry cycle.

## 6. Rule Evaluation

Rules are evaluated:

- Periodically (via background worker)
- Manually (via admin panel or CLI trigger)

Admin panel trigger always run with default task values.

### 6.1 CLI Trigger:
```bash
docker compose exec web python manage.py run_process_telemetry
```

CLI Flags:
| Flag | Description |
|------|------------|
| `--start (int)` | Specifies the cursor start position. If omitted, the task uses its default behavior. |
| `--batch_size (int)` | Number of telemetry entries to process during the task (default: 1000). |
| `--update_cursor (bool)` | Determines whether the cursor should be updated after the run (default: true). |


Each evaluation:

- Computes condition result
- Records evaluation metadata
- Optionally generates an event

## 7. Cooldown Behavior
Cooldown is set universally for all rule through the
`DJANGO_RULE_COOLDOWN_MINUTES` .env variable