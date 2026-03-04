# Example payloads: Rules & Events

This document provides **copy/paste-ready JSON examples** for the **Rules** and **Events** parts of the API.

---

## Rules

### Create a rule — `POST /api/v1/rules`

**Request body** (`RuleCreate`)

```json
{
  "name": "Low Vibration Alert Lathe",
  "description": "Alerts maintenance when vibration drops below expected operating range",
  "condition": {
    "type": "leaf",
    "operator": "gt",
    "threshold": 5,
    "window_seconds": 15,
    "occurances": 3
  },
  "action_config": [
    {
      "type": "notification",
      "template_id": 5
    },
    {
      "type": "stop_machine",
      "machine_id": "CNC-002"
    }
  ],
  "is_enabled": true,
  "device_id": "a80031eb-189a-49d5-93ab-11bd465143e9"
}
```

**Notes**
- `condition`: Additional info and formating can be found at [rules.md](./rules.md)
- `action_config` a list containing notifications or stop_machine types

   - `notifications`:
      - `template_id`: template id used for notification, coresponds to notification_template id.

   - `stop_machine`:
      - `machine_id`: corresponds to a device serial_number 
  

**Response** (`Rules`)
```json
{
  "name": "Low Vibration Alert Lathe",
  "description": "Alerts maintenance when vibration drops below expected operating range",
  "condition": {
    "type": "leaf",
    "operator": "gt",
    "threshold": 5,
    "window_seconds": 15,
    "occurances": 3
  },
  "action_config": [
    {
      "type": "notification",
      "recipients": ["test@test.com"],
      "template_id": 5
    },
    {
      "type": "stop_machine",
      "machine_id": "CNC-002"
    }
  ],
  "last_triggered_at": "2026-01-16T17:30:00Z",
  "is_enabled": true
}
```

---

### Enable/disable a rule — `PATCH /api/v1/rules/{id}`

**Request body** (toggle activation)

Enable:
```json
{ "enabled": true }
```

Disable:
```json
{ "enabled": false }
```

**Response** (`Rules`) — same shape as Rule get/create responses.

---

### Get a rule — `GET /api/v1/rules/{id}`

**Response** (`Rules`)

```json
{
  "name": "Low Vibration Alert Lathe",
  "description": "Alerts maintenance when vibration drops below expected operating range",
  "condition": {
    "type": "leaf",
    "operator": "gt",
    "threshold": 5,
    "window_seconds": 15,
    "occurances": 3
  },
  "action_config": [
    {
      "type": "notification",
      "recipients": ["test@test.com"],
      "template_id": 5
    }
  ],
  "last_triggered_at": "2026-01-16T17:30:00Z",
  "is_enabled": true
}
```

---

### Trigger an inbound/external rule — `POST /api/v1/rules/inbound/{inbound_id}`

**Request body** is defined as a free-form object (`additionalProperties: true`).
InboundRules are created for external rule-event triggering pipeline, it can accept anything in the json body and will

be transformed using the [inbound_rules.json](../backend/apps/rules/services/inbound_map.json)

Here’s an example that exists in [inbound_rules.json](../backend/apps/rules/services/inbound_map.json):


```json
POST /api/v1/rules/inbound/1234
```
```json
{
    "trigger": 133322,
    "cooldown": 25,
    "aparatus": 6652,
    "message": "Rule triggered",
    "offender": {
        "temp": 15.123411
    },
    "actions": [
        {"address": "bob@gmail.com", "person": "bob"},
        {"address": "vance@gmail.com", "person": "vance"}
    ]
}
```

**Response** (`InboundRules`)

```json
{
  "type": "external",
  "rule_id": "133322",
  "device_id": "6652",
  "timestamp": "2026-02-28T08:59:47.720763+00:00",
  "severy": "warning",
  "message": "Rule triggered",
  "execution_results": [],
  "telemetry_snapshot": {
    "value": 15,
    "start": "2026-02-28T09:02:55.979981+00:00",
    "end": "2026-02-28T09:02:55.979981+00:00"
  },
  "action_config": [
    { "type": "notification", "template_id": 1 }
  ],
  "notifications": [],
  "cooldown_min": 25
}
```

**Notes**
- `telemetry_snapshot` required end/start and value, however, all those values can be substituted
- `action_config` and `notifications` are **free-form arrays** (`items: {}`), so their internal structures are not constrained by the OpenAPI schema. \
---

## Events

### List events — `GET /api/v1/events`

**Response** (`EventListResponse`)

```json
{
  "data": [
    {
      "id": 321,
      "rule_id": "29e31015-4733-49f3-855a-ef7f30e6c147",
      "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "severity": "warning",
      "message": "Warning: Device-01 temperature 84.3C",
      "status": "acknowledged",
      "acknowledged": true,
      "fired_at": "2026-02-08T18:22:31Z",
      "created_at": "2026-02-08T18:22:31Z",
      "execution_results": [
        { "type": "notification", "template_id": 5, "status": "completed" }
      ],
      "telemetry_snapshot": {
        "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "timestamp": "2026-02-08T18:22:00Z",
        "payload": { "value": 84.3 }
      },
      "payload": { "value": 84.3 }
    }
  ],
  "pagination": {
    "page": 2,
    "page_size": 10,
    "total": 134,
    "total_pages": 14,
    "next_page": 3,
    "prev_page": 1
  }
}
```

---

### Get a single event — `GET /api/v1/events/{event_id}`

**Response** (`EventResponse`)

```json
{
  "data": {
    "id": 321,
    "rule_id": "29e31015-4733-49f3-855a-ef7f30e6c147",
    "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "severity": "warning",
    "message": "Warning: Device-01 temperature 84.3C",
    "status": "new",
    "acknowledged": false,
    "fired_at": "2026-02-08T18:22:31Z",
    "created_at": "2026-02-08T18:22:31Z",
    "execution_results": [],
    "telemetry_snapshot": null,
    "payload": null
  }
}
```

---

### Acknowledge an event — `POST /api/v1/events/{event_id}/ack`

**Response** (`EventResponse`)

```json
{
  "data": {
    "id": 321,
    "rule_id": "29e31015-4733-49f3-855a-ef7f30e6c147",
    "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "severity": "warning",
    "message": "Warning: Device-01 temperature 84.3C",
    "status": "acknowledged",
    "acknowledged": true,
    "fired_at": "2026-02-08T18:22:31Z",
    "created_at": "2026-02-08T18:22:31Z",
    "execution_results": [
      { "type": "notification", "template_id": 5, "status": "completed" }
    ],
    "telemetry_snapshot": {
      "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "timestamp": "2026-02-08T18:22:00Z",
      "payload": { "value": 84.3 }
    },
    "payload": { "value": 84.3 }
  }
}
```

---

### Resolve an event — `POST /api/v1/events/{event_id}/resolve`

**Response** (`EventResponse`)

```json
{
  "data": {
    "id": 321,
    "rule_id": "29e31015-4733-49f3-855a-ef7f30e6c147",
    "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "severity": "warning",
    "message": "Warning: Device-01 temperature 84.3C",
    "status": "resolved",
    "acknowledged": true,
    "fired_at": "2026-02-08T18:22:31Z",
    "created_at": "2026-02-08T18:22:31Z",
    "execution_results": [
      { "type": "notification", "template_id": 5, "status": "completed" }
    ],
    "telemetry_snapshot": {
      "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
      "timestamp": "2026-02-08T18:22:00Z",
      "payload": { "value": 84.3 }
    },
    "payload": { "value": 84.3 }
  }
}
```

---

## Quick reference: Event fields

`Event` includes: `id`, `rule_id`, `device_id`, `severity`, `message`, `status`, `acknowledged`, `fired_at`, `created_at`, plus optional `execution_results`, `telemetry_snapshot`, `payload`.