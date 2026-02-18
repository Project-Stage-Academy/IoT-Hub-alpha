# Schema Notes (Events + Notifications)

This document describes the **current** database schema and semantics for
Events and Notifications in this project. It reflects the existing models and
does **not** propose new fields.

---

## Events

**Model:** `apps.events.models.Event`  
**DB table:** `events`

### Fields
- `id` (BigAutoField)  
  Primary key.

- `rule_id` (FK → `rules.id`)  
  Rule that fired and produced the event.

- `timestamp` (DateTime, auto_now_add)  
  When the event was recorded.  
  In API responses this is exposed as `created_at` and as fallback for `fired_at`.

- `severity` (enum: `critical`, `warning`, `info`)  
  Derived from notification template priority.

- `message` (text)  
  Human‑readable description rendered from the notification template.

- `execution_results` (JSON)  
  List of action results for this event.  
  Example item:
  ```json
  {
    "type": "notification",
    "template_id": 1,
    "status": "sent",
    "recipient_count": 2,
    "sent_count": 2,
    "failed_count": 0,
    "pending_count": 0,
    "last_attempt_at": "2026-02-09T00:01:25Z",
    "completed_at": "2026-02-09T00:01:25Z"
  }
  ```
  `status` is updated as deliveries complete (`queued`/`sent`/`failed`).

- `telemetry_snapshot` (JSON, nullable)  
  Minimal telemetry context captured at trigger time:
  ```json
  {
    "device_id": "uuid",
    "timestamp": "ISO-8601",
    "payload": {
      "values": [12.3, 13.7],
      "start": "ISO-8601",
      "end": "ISO-8601"
    }
  }
  ```

- `status` (enum: `new`, `acknowledged`, `resolved`)  
  Used for acknowledgement flow.

### Indexes
Indexes are defined for efficient filtering by rule and status/time.

---

## Notification Templates

**Model:** `apps.notifications.models.NotificationTemplate`  
**DB table:** `notification_templates`

### Fields
- `id` (BigAutoField)
- `name` (unique)
- `message_template` (text)
- `recipients` (JSON list)  
  Example:
  ```json
  [
    {"type": "email", "address": "ops@factory.com"},
    {"type": "sms", "phone": "+380501234567"},
    {"type": "webhook", "url": "https://webhook.site/…"}
  ]
  ```
- `priority` (1..4, low → critical)
- `retry_count`, `retry_delay_minutes`
- `is_active`
- `created_at`, `updated_at`

---

## Notification Deliveries

**Model:** `apps.notifications.models.NotificationDelivery`  
**DB table:** `notification_deliveries`

### Fields
- `id` (BigAutoField)
- `event_id` (FK → `events.id`)
- `template_id` (FK → `notification_templates.id`)
- `notification_type` (enum: `email`, `sms`, `webhook`)
- `recipient_address`
- `recipient_name` (nullable)
- `rendered_message`
- `status` (enum: `pending`, `sent`, `failed`)
- `attempt_count`
- `last_attempt_at`
- `error_message` (nullable)
- `sent_at` (nullable)
- `created_at`

### Semantics
Each event produces **one delivery per recipient**.  
Delivery attempts are tracked in `attempt_count`, with retry/backoff for webhooks.

---

## API Mapping (Events)

The Events API exposes:
- `fired_at` → `Event.telemetry_snapshot.timestamp` (fallback: `Event.timestamp`)
- `created_at` → `Event.timestamp`
- `acknowledged` → `status != new`
- `payload` → `telemetry_snapshot.payload`
