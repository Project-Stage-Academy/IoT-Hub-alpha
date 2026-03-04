# Rule Events Admin Usage Guide

---

## General Rule / Event Flow

### Current (Event-Driven, Real-Time) — Internal

```
Device → Kafka (telemetry.raw)
  ↓
db_writer → Kafka (telemetry.clean)  [validation + normalization]
  ↓
RulesConsumer → trigger_engine_realtime() → Kafka (events topic)
  ↓
EventConsumer → event_handler() + action_dispatch() → Event DB
```

**Explanation**

1. Devices send telemetry.
2. Telemetry is validated and normalized.
3. Rules are evaluated in real time.
4. When a rule triggers, an event is produced.
5. Events are processed and persisted in the Event database.
6. Actions (notifications, machine control, etc.) are dispatched.

---

### Current (Event-Driven, Real-Time) — External

```
POST /api/v1/rules/inbound/{inbound_id}
  ↓
EventConsumer → event_handler() + action_dispatch() → Event DB
```

External systems may directly submit events without going through telemetry ingestion.

These events bypass rule evaluation and are handled as already-triggered events.

---

## Admin Usage

There are currently **two ways** to create, update, read, and delete rules and events:

- **Django Admin UI**  
  http://127.0.0.1/admin (when deployed locally)

- **REST API**

API endpoints and payload examples can be found here:

[example-payloads-rules-events.md](./example-payloads-rules-events.md)

The Django admin panel is largely self-explanatory and contains inline descriptions.

---

# Tutorials and Sample Workflows

---

## Notification Template Creation

Notification templates define **where messages should be delivered** when a rule triggers.

You can think of a notification template as a **contact book**:

```
Rule triggers
   ↓
Event created
   ↓
Template is resolved
   ↓
Recipients retrieved
   ↓
Delivery attempts executed (with retry policy)
```

Templates may contain:

- email recipients
- phone numbers
- webhook URLs

> **NOTE**
>
> Notifications currently **do not have a public API endpoint** and can only be created via the Django Admin UI.

---

## Rule Registration (Internal Rules)

Before creating a functional rule, the following must exist:

- A registered **device**
- A **notification template** (if notifications are used)

---

### Example Setup

Device:

```
a80031eb-189a-49d5-93ab-11bd465143e9
```

Notification template:

```
template_id = 5
```

---

### Create Rule

```
POST /api/v1/rules
```

```json
{
  "name": "Low Vibration Alert Lathe",
  "description": "Alerts maintenance when vibration drops below expected operating range",
  "condition": {
    "type": "leaf",
    "operator": "gt",
    "threshold": 5
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

---

### What This Rule Does

The rule triggers when:

```
device value > 5
```

Once triggered:

1. A notification is sent using template `5`
2. The machine `CNC-002` receives a stop command
3. An Event record is created

Additional information about rule conditions can be found in [rules.md](./rules.md).

> **NOTE**
>
> Rules can also be created via the Django Admin panel.  
> Since the admin UI already contains detailed help text, it is not covered here.

---

## Rule Registration (External Rules)

External systems submit already-triggered rules using:

```
POST /api/v1/rules/inbound/{inbound_id}
```

This endpoint:

- accepts **any JSON structure**
- performs transformation using:

```
backend/apps/rules/services/inbound_map.json
```

If the payload validates after transformation:

```
Inbound payload
   ↓
Mapped to internal structure
   ↓
Published to events topic
   ↓
Processed like native events
```

External events differ slightly from internal ones:

- contain `"type": "external"`
- may use custom notification behavior
- do not originate from telemetry rule evaluation

---

# FAQ — Rules & Events

---

## Frequently Asked Questions

### What is the difference between a Rule and an Event?

**Rule**
- Defines when something should happen.
- Evaluates incoming telemetry.

**Event**
- Represents something that already happened.
- Created when a rule triggers or an external event is received.

---

### When is an Event created?

An event is created when:

- a rule condition evaluates to true, or
- an external system calls `/rules/inbound/{inbound_id}`.


---

### Can I create rules without notification templates?

Yes. Notifications are optional.

---

### What happens if a notification fails?

The notification system applies retry policies defined in the template configuration.

---

### Are external rules evaluated against conditions?

No. External inbound rules are treated as already triggered events.

---

### Where should validation happen?

Validation occurs in multiple stages:

1. ingestion validation (`telemetry.raw → telemetry.clean`)
2. inbound mapping validation (external events)
3. rule execution validation

---

### Can rules be disabled without deleting them?

Yes:

```json
{ "enabled": false }
```

---

### Does disabling a rule delete historical events?

No. Events are immutable historical records.

---

### Why Kafka instead of direct DB writes?

Kafka provides:

- buffering
- backpressure handling
- replay capability
- decoupled processing
- horizontal scalability

---

### How do I debug why a rule didn’t trigger?

Check:

1. telemetry exists in `telemetry.clean`
2. rule is enabled
3. device_id matches
4. condition structure is valid
5. RulesConsumer is running
