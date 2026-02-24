# External Event Processor

## Overview

The **External Event Processor** is responsible for receiving rule-triggered
events from external systems, transforming them into the internal event
schema, validating them, and persisting them into the platform.

---

## Responsibilities

The processor performs the following steps:

1. **Receive inbound event payload**
   - HTTP endpoint: `POST /api/v1/rules/inbound/<inbound_id>`
   - Accepts JSON payload

2. **Apply Transformation Rules**
   - Uses a configurable JSON mapping
   - located at: backend/apps/rules/services/inbound_map.json
   - Supports:
     - Field renaming (`from`)
     - Default values (`default`)
     - Type casting (`cast`)
     - Nested objects (`inner_dict`)
     - List transformations (`list`)

3. **Validate Against Pydantic Schema**
   - Validates transformed payload using `ExternalEventMessage`
   - Extra fields are ignored
   - Invalid payloads raise `ValidationError`

4. **Persist Event**
   - Creates `Event` record
   - Optionally links to internal `Rule` (FK)
   - Stores external rule identifier as ID

---

## Request Example

### Incoming Payload Example 1
```
POST /api/v1/rules/inbound/1234
```
```json
{
    "trigger": 133322,
    "cooldown": 255,
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

### Incoming Payload Example 2
```
POST /api/v1/rules/inbound/1111
```
```json
{
    "place": "DVN-11",
    "cd": 15,
    "device": "VBR-15",
    "trigger_device": {
        "vibration": 15.123411,
        "metric": "c"
    },
    "actions": [
        {"address": "dwight@gmail.com", "person": "dwight"},
        {"address": "jim@gmail.com", "person": "jim"}
    ]
}
```

### Incoming Payload Example 3
```
POST /api/v1/rules/inbound/4454
```
```json
{
    "rule": "my-custom-rule",
    "device-5523LONG": "VBR-15"
}
```

## Validation
Validation is done using pydantic AFTER transformation according to the map was complete.

inbound_id in URL path is REQUIRED

the ONLY required body fields are:
- rule_id
- device_id

## Future extension:
- Authentication via JWT token
- Async operation via celery workers (if load increases)
- Deal-letter queue integration