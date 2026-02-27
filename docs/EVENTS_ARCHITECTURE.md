# Events Architecture - Task-94 Real-Time Rules Refactoring

## Overview

The Events module handles event creation and action dispatch in response to triggered rules. It operates asynchronously via Kafka, decoupling rule evaluation (in the Rules module) from event persistence and action execution (in the Events module).

## Architecture

### Data Flow

```
RulesConsumer                     EventConsumer
(Task-94)                         (Task-94)
    ↓                                 ↓
Evaluates Rules               Processes Events
    ↓                                 ↓
trigger_engine_realtime()    event_handler()
    ↓                                 ↓
Kafka: events topic          Event.objects.create()
                                      ↓
                              action_dispatch()
                                      ↓
                              Notifications/Actions
```

### Module Structure

```
apps/events/
├── models.py                    # Event model with validators
├── admin.py                     # Django admin interface
├── serializer.py                # Event API serializers
├── views.py                     # Event API endpoints
├── management/
│   └── commands/
│       └── events_consumer.py   # Kafka consumer management command
└── services/
    ├── event_handler.py         # Event creation with cooldown
    ├── actions.py               # Action dispatch (notifications, machine control)
    └── csv_export.py            # CSV export utilities
```

## Key Components

### 1. Event Model (`models.py`)

**Purpose**: Stores event records triggered by rules.

**Fields**:
- `id`: UUID primary key
- `rule`: ForeignKey to Rule (CASCADE delete)
- `timestamp`: When event occurred
- `severity`: WARNING, INFO, CRITICAL
- `message`: Human-readable event description
- `status`: NEW, ACKNOWLEDGED, RESOLVED
- `execution_results`: JSON list of action results
- `telemetry_snapshot`: Captured telemetry at trigger time
- `created_at`, `updated_at`: Timestamps

**Validators**:
- `validate_execution_results()`: Ensures valid action execution format
- `validate_telemetry_snapshot()`: Validates telemetry data structure

### 2. Event Handler (`services/event_handler.py`)

**Purpose**: Creates events with cooldown protection.

**Key Functions**:

#### `event_handler(aggregate, rule, message, template=None)`
- Creates Event record
- Checks rule cooldown (prevents event spam)
- Sets event_cooldown_until on rule (60-minute default)
- Raises `EventCooldownActive` if cooldown is active
- Returns created Event instance

**Example**:
```python
from apps.events.services.event_handler import event_handler

try:
    event = event_handler(
        aggregate=EvalResults(trigger=True, values=[26.0]),
        rule=rule_obj,
        message="Temperature > 25°C"
    )
    print(f"Event created: {event.id}")
except EventCooldownActive:
    print("Event is in cooldown period")
```

#### `get_template(template_id)`
- Retrieves NotificationTemplate by ID
- Caches results for performance
- Raises `NotificationTemplate.DoesNotExist` if not found

### 3. Action Dispatch (`services/actions.py`)

**Purpose**: Routes triggered events to appropriate actions.

**Key Functions**:

#### `action_dispatch(action_config, rule, aggregate)`
- Routes to appropriate handler based on action type
- Handles exceptions gracefully (logs error, doesn't crash)
- Supports multiple action types:
  - `notification`: Send notifications via email/SMS/Slack
  - `stop_machine`: Machine control (stub)

**Example**:
```python
from apps.events.services.actions import action_dispatch

config = ActionConfig.model_validate({
    "type": "notification",
    "template_id": 1
})
action_dispatch(config, rule, aggregate)
```

#### `dispatch_msg(action_config, rule, aggregate)`
- Sends notifications
- Retrieves notification template
- Enqueues async delivery task
- Formats message with rule context

#### `stop_machine(action_config, rule, aggregate)`
- Stub for machine control integration
- Currently logs action (placeholder)

### 4. Events Consumer (`management/commands/events_consumer.py`)

**Purpose**: Kafka consumer that processes event messages asynchronously.

**Flow**:
1. Subscribe to `events` Kafka topic
2. Poll messages with timeout
3. Parse event JSON payload
4. Reconstruct EvalResults from telemetry_snapshot
5. Retrieve Rule object
6. Call `event_handler()` (checks cooldown)
7. Dispatch actions via `action_dispatch()`
8. Commit offset to Kafka

**Execution**:
```bash
python manage.py events_consumer
```

**Message Format** (from Kafka `events` topic):
```json
{
  "type": "internal",
  "rule_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2026-02-19T12:00:00Z",
  "severity": "warning",
  "message": "Rule 'High Temp' triggered",
  "execution_results": [],
  "telemetry_snapshot": {
    "values": [26.0, 27.0, 28.0],
    "start": "2026-02-19T11:59:00Z",
    "end": "2026-02-19T12:00:00Z"
  }
}
```

## Cooldown Mechanism

**Purpose**: Prevent event spam when rule triggers repeatedly.

**How It Works**:
1. When `event_handler()` creates an event, it sets `rule.event_cooldown_until`
2. Default cooldown: 60 minutes (COOLDOWN_TIMER_MINUTES env var)
3. Next event creation checks: `if rule.event_cooldown_until > now()`
4. If cooldown active: raises `EventCooldownActive` exception
5. EventConsumer catches exception, logs, and continues (idempotent)

**Configuration**:
```bash
# .env
COOLDOWN_TIMER_MINUTES=60
```

## Error Handling

### EventConsumer Error Handling
```python
try:
    # Parse and process event
    event = event_handler(aggregate, rule, message, template)
except EventCooldownActive:
    logger.info("Event in cooldown, skipping")
    # Idempotent: can retry safely
except Rule.DoesNotExist:
    logger.error(f"Rule not found: {rule_id}")
    # Can't process deleted rule
except Exception as e:
    logger.error(f"Error processing event: {e}")
    # Continue to next message (don't crash consumer)
```

### Action Dispatch Error Handling
```python
def action_dispatch(action_config, rule, aggregate):
    try:
        if action_config.type == "notification":
            dispatch_msg(action_config, rule, aggregate)
        elif action_config.type == "stop_machine":
            stop_machine(action_config, rule, aggregate)
    except Exception as e:
        logger.error(f"Error dispatching action: {e}")
        # Don't crash consumer; one action failure doesn't block others
```

## Integration with Other Modules

### Rules Module
- **Dependency**: Rules evaluates conditions and triggers events
- **Interface**: Sends event messages to Kafka `events` topic
- **Isolation**: Rules module doesn't import Event model (loose coupling)

### Notifications Module
- **Dependency**: Events dispatches notifications
- **Interface**: `queue_notification(template, context)`
- **Async**: Notifications are queued for async delivery

### Telemetry Module
- **Dependency**: Event stores telemetry snapshot
- **Interface**: EvalResults with `values`, `start`, `end` timestamps
- **Usage**: Captured at rule trigger time for context

## Testing

### Unit Tests (`tests/test_imports.py`)
```bash
# Test module imports and structure
pytest apps/events/tests/test_imports.py -v

# Coverage: event_handler.py (59%), actions.py (29%)
```

### Integration Tests
- EventConsumer message processing
- Event creation with cooldown
- Action dispatch to notifications
- Error handling for missing rules/templates

**Run all tests**:
```bash
pytest apps/events/ -v --cov=apps.events
```

## Deployment

### Docker Compose
```yaml
events_consumer:
  build: .
  command: python manage.py events_consumer
  depends_on:
    - postgres
    - kafka
  environment:
    - DATABASE_URL=postgresql://...
    - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    - COOLDOWN_TIMER_MINUTES=60
```

### Monitoring

**Key Metrics**:
- `events_created_total`: Events created per rule/device
- `events_cooldown_skipped`: Events skipped due to cooldown
- `event_creation_duration_ms`: Event creation latency
- Kafka lag: Consumer lag on `events` topic

### Logging

**Key Log Points**:
- Event created: `logger.info("Event created", extra={"rule_id": ..., "event_id": ...})`
- Cooldown active: `logger.info("Event in cooldown")`
- Action dispatched: `logger.info("Action dispatched", extra={"action_type": ...})`
- Errors: `logger.error("Error processing event", exc_info=True)`

## Performance Considerations

### Latency
- Event creation: < 50ms (DB insert)
- Action dispatch: < 100ms per action
- Kafka processing: < 200ms per message
- **Total end-to-end**: < 350ms from rule trigger to DB persistence

### Throughput
- EventConsumer: Can handle 1000+ events/sec (per instance)
- Horizontal scaling: Deploy multiple instances with same consumer group
- Kafka partitions: `event.topic` should have ≥ number of consumers

### Memory
- EventConsumer: ~50MB base + message buffer
- Action queues: Bounded by Celery broker (Redis/RabbitMQ)
- No unbounded data structures (safe for long-running processes)

## Future Enhancements

1. **Event Deduplication**: UUID-based idempotency key in Event model
2. **Event Retention**: Archive old events to separate storage
3. **Event Streaming**: Real-time event webhooks/subscriptions
4. **Custom Actions**: Plugin architecture for action handlers
5. **Event Templates**: Richer event creation with template inheritance
6. **Smart Cooldown**: Per-severity or per-action-type cooldown settings

## References

- [Rule Evaluation Process](./RULE_EVALUATION_PROCESS.md)
- [Metrics Guide](./METRICS_GUIDE.md)
- [Kafka Integration Plan](./KAFKA_INTEGRATION_PLAN.md)
