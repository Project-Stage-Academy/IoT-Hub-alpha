## 1. Overview

Rules define conditions that are evaluated against incoming telemetry data.
When a rule evaluates to `true`, an event is generated and optional actions (notifications, automations) are triggered.

Key concepts:

- Rule – declarative definition of what to evaluate
- Condition – logical expression evaluated against telemetry
- Evaluation – execution of a rule for a given telemetry window
- Event – persistent record created when a rule is triggered

## 2. Rule Model (Conceptual)

A rule consists of:

| Field         | Description                                             |
| ------------- | ------------------------------------------------------- |
| id            | Unique rule identifier                                  |
| name          | Human-readable name                                     |
| description   | Short human-readable description                        |
| action_config | JSON object of instruction to execute upon rule trigger |
| device        | Device the rule applies to                              |
| enabled       | Whether the rule is active                              |
| conditions    | Condition definition (JSON)                             |
| created_at    | Creation timestamp                                      |
| updated_at    | Last modification timestamp                             |

## 3. Creating a Rule (API)

Endpoint

```http
POST /api/v1/rules/
Authorization: Bearer <jwt_token>
```

Example - Threshold Rule:

```json
{
  "device": "8971c22c-33c4-4d34-be7a-dea15dd1e851",
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
      "template_id": "2",
    }
  ],
  "is_enabled": true
}
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
Authorization: Bearer <jwt_token>
```
```json
{
    "enabled": false
}
```
Disabled rules:

- Are not evaluated
- Do not generate events
- Preserve evaluation history

Enable a Rule
```json
{
  "enabled": true
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