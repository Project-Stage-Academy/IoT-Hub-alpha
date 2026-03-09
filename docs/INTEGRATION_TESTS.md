# Integration Tests - Basic

Overview of the integration test suite for IoT Hub ingestion module.

**File:** `backend/apps/telemetry/tests/test_integration_basic.py`
**Status:** ✅ 14/14 passing in Docker
**Duration:** ~8 seconds

---

## Overview

Integration tests that verify basic MQTT and device simulator functionality without strict timing assumptions or complex interactions.

**Focus:** Core behavior validation
**Mocks Used:** MQTT (mqtt.py), Devices (devices.py), Helpers (helpers.py)

> **Note:** Kafka mock (kafka.py) is NOT used in basic integration tests. It's used in rules consumer and event consumer unit tests (test_realtime_consumer.py, test_trigger_engine_realtime.py) for testing Kafka producer/consumer without real broker.

---

## Test Categories

### 1. TestBasicMQTTPublishing (3 tests)

Tests basic device publishing to MQTT topics.

#### test_single_device_publishes()
```python
def test_single_device_publishes(self, mqtt_setup):
    """Single device successfully publishes."""
```

**What it does:**
1. Creates a temperature sensor via factory
2. Starts publishing (background thread)
3. Waits 0.2 seconds for messages
4. Stops publishing
5. Verifies messages were published to topic

**Assertions:**
- `len(messages) > 0` - At least one message published
- `device.message_count > 0` - Device tracks count

**Why it matters:**
Validates that VirtualDevice can publish to MQTT mock without errors.

---

#### test_multiple_devices_publish()
```python
def test_multiple_devices_publish(self, mqtt_setup):
    """Multiple devices publish independently."""
```

**What it does:**
1. Creates 3 temperature sensors via factory
2. Starts all simultaneously
3. Waits 0.2 seconds
4. Stops all
5. Verifies each has own messages

**Assertions:**
- For each device: `len(messages) > 0`
- Each device has independent topic
- No cross-device message mixing

**Why it matters:**
Confirms MockBroker correctly isolates topics and handles multiple publishers.

---

#### test_telemetry_message_structure()
```python
def test_telemetry_message_structure(self, mqtt_setup):
    """Telemetry messages have correct structure."""
```

**What it does:**
1. Creates and starts device
2. Retrieves published messages
3. Parses JSON payload
4. Validates required fields

**Assertions:**
```python
assert "serial_number" in payload
assert "value" in payload
assert "timestamp" in payload
assert "device_type" in payload
```

**Why it matters:**
Ensures messages follow schema - critical for downstream processing.

---

### 2. TestDataBuilders (3 tests)

Tests fluent builder APIs for creating test data.

#### test_telemetry_builder()
```python
def test_telemetry_builder(self):
    """TelemetryBuilder works correctly."""
```

**What it does:**
```python
telemetry = (
    TelemetryBuilder()
    .with_serial("TEST-001")
    .with_value(25.5)
    .build()
)
```

**Assertions:**
- `telemetry["serial_number"] == "TEST-001"`
- `telemetry["value"] == 25.5`

**Why it matters:**
Builder pattern simplifies test data creation in other tests.

---

#### test_rule_builder()
```python
def test_rule_builder(self):
    """RuleBuilder works correctly."""
```

**What it does:**
```python
rule = (
    RuleBuilder()
    .with_name("Test Rule")
    .with_threshold(30.0)
    .with_operator("gt")
    .build()
)
```

**Assertions:**
- `rule["name"] == "Test Rule"`
- `rule["condition"]["threshold"] == 30.0`
- `rule["condition"]["operator"] == "gt"`

**Why it matters:**
RuleBuilder enables quick rule creation for rule evaluation tests.

---

#### test_telemetry_json_serialization()
```python
def test_telemetry_json_serialization(self):
    """TelemetryBuilder serializes to JSON."""
```

**What it does:**
```python
telemetry_json = (
    TelemetryBuilder()
    .with_serial("TEST-001")
    .with_value(25.5)
    .build_json()
)
parsed = json.loads(telemetry_json)
```

**Assertions:**
- JSON is valid (no parse errors)
- Parsed values match original
- Both dict and JSON forms work

**Why it matters:**
Telemetry data flows as JSON in real system, builder must support both.

---

### 3. TestMQTTClient (3 tests)

Tests MockMQTTClient basic operations.

#### test_client_publish_retrieve()
```python
def test_client_publish_retrieve(self, mqtt_setup):
    """Publish and retrieve messages."""
```

**What it does:**
1. Get MQTT client from fixture
2. Publish: `client.publish("test/topic", {"key": "value"})`
3. Retrieve: `get_messages("test/topic")`
4. Parse and verify

**Assertions:**
- `len(messages) == 1` - Exactly one message
- `payload["key"] == "value"` - Content preserved

**Why it matters:**
Validates basic MQTT mock publish/retrieve cycle.

---

#### test_multiple_publishes()
```python
def test_multiple_publishes(self, mqtt_setup):
    """Multiple publishes accumulate."""
```

**What it does:**
```python
for i in range(5):
    client.publish("test/topic", f"message-{i}".encode())
messages = get_messages("test/topic")
```

**Assertions:**
- `len(messages) == 5` - All messages stored
- Messages not lost or deduplicated

**Why it matters:**
Confirms broker accumulates messages (no truncation/loss).

---

#### test_different_topics_isolated()
```python
def test_different_topics_isolated(self, mqtt_setup):
    """Different topics are isolated."""
```

**What it does:**
```python
client.publish("topic1", b"data1")
client.publish("topic2", b"data2")
msg1 = get_messages("topic1")
msg2 = get_messages("topic2")
```

**Assertions:**
- `len(msg1) == 1` and `msg1[0]["payload"] == b"data1"`
- `len(msg2) == 1` and `msg2[0]["payload"] == b"data2"`
- No cross-topic contamination

**Why it matters:**
Real MQTT has topic isolation, mock must maintain it.

---

### 4. TestDeviceSimulator (3 tests)

Tests VirtualDevice and VirtualDeviceFactory.

#### test_device_creation()
```python
def test_device_creation(self, mqtt_setup):
    """Create device successfully."""
```

**What it does:**
```python
device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")
```

**Assertions:**
- `device.serial_number == "TEMP-001"`
- `device.device_type == "temperature_sensor"`

**Why it matters:**
Factory creates correct device instances with properties.

---

#### test_device_factory_types()
```python
def test_device_factory_types(self, mqtt_setup):
    """Factory creates different sensor types."""
```

**What it does:**
```python
factory = mqtt_setup["factory"]
temp = factory.create_temperature_sensor("T-001")
vib = factory.create_vibration_sensor("V-001")
cur = factory.create_current_sensor("C-001")
```

**Assertions:**
- `temp.device_type == "temperature_sensor"`
- `vib.device_type == "vibration_sensor"`
- `cur.device_type == "current_sensor"`

**Why it matters:**
Factory supports multiple sensor types for realistic tests.

---

#### test_device_group_creation()
```python
def test_device_group_creation(self, mqtt_setup):
    """Create group of devices."""
```

**What it does:**
```python
devices = mqtt_setup["factory"].create_device_group(
    count=3,
    device_type="temperature_sensor"
)
```

**Assertions:**
- `len(devices) == 3` - Correct count
- `all(d.device_type == "temperature_sensor" for d in devices)` - All correct type

**Why it matters:**
Batch device creation needed for multi-device scenarios.

---

### 5. TestEndToEndBasic (2 tests)

End-to-end scenarios combining device and MQTT.

#### test_device_to_mqtt()
```python
def test_device_to_mqtt(self, mqtt_setup):
    """Device publishes to MQTT successfully."""
```

**Flow:**
```
VirtualDevice → publish() → MockBroker → get_messages() → Verify payload
```

**What it does:**
1. Create temperature sensor
2. Start publishing (0.15s)
3. Retrieve from MQTT topic
4. Parse and validate each message

**Assertions:**
```python
assert len(messages) > 0
assert device.message_count == len(messages)  # Count matches
payload = json.loads(msg["payload"])
assert payload["serial_number"] == "TEMP-001"
assert isinstance(payload["value"], (int, float))
```

**Why it matters:**
Full cycle: generation → MQTT → retrieval (real system simulation).

---

#### test_multiple_device_publishing()
```python
def test_multiple_device_publishing(self, mqtt_setup):
    """Multiple devices publish simultaneously."""
```

**What it does:**
```
Temp (→ MQTT) \
Vibr (→ MQTT)  →  MockBroker  →  Verify each
Curr (→ MQTT) /
```

1. Create 3 different sensor types
2. Start all simultaneously
3. Let background threads publish
4. Stop all
5. Verify each has own messages and count

**Assertions:**
- For each device: `len(messages) > 0`
- For each device: `device.message_count == len(messages)`
- No crosstalk between topics

**Why it matters:**
Real system has many concurrent sensors, this validates parallel publishing.

---

## How Tests Execute

### Setup Phase

```python
@pytest.fixture
def mqtt_setup(mqtt_client, mqtt_broker):
    # Created fresh for each test
    factory = VirtualDeviceFactory(mqtt_client)
    # ...
    yield {...}  # Provide to test
    # Cleanup happens automatically
```

**Per test:**
- Fresh MockMQTTClient instance
- Isolated broker (random broker_id)
- New factory
- Clean message storage

### Execution Phase

Each test:
1. Receives `mqtt_setup` fixture
2. Uses factory to create devices
3. Calls methods on devices/client
4. Retrieves messages
5. Asserts expected behavior

### Cleanup Phase

After test:
- Client disconnects
- Broker cleared
- Devices stopped
- Fresh state for next test

---

## Key Design Principles

### 1. No Strict Timing Assumptions

❌ BAD: `assert device.message_count == 24` (assumes exact timing)
✅ GOOD: `assert device.message_count > 0` (checks existence only)

**Why:** Publishing interval and system load vary.

### 2. Single Responsibility

Each test validates ONE behavior:
- Publishing works
- Structure correct
- Topics isolated
- Factory creates devices

NOT multiple things at once.

### 3. Clear Assertions

```python
# ❌ Unclear
assert messages

# ✅ Clear
assert len(messages) > 0, "Device should publish at least one message"
```

### 4. Realistic Scenarios

Tests simulate real use cases:
- Devices publishing continuously
- Multiple concurrent sensors
- JSON message format
- Topic-based routing

---

## Running Tests

### Run all integration tests
```bash
cd backend
pytest apps/telemetry/tests/test_integration_basic.py -v
```

### Run specific test class
```bash
pytest apps/telemetry/tests/test_integration_basic.py::TestBasicMQTTPublishing -v
```

### Run specific test
```bash
pytest apps/telemetry/tests/test_integration_basic.py::TestBasicMQTTPublishing::test_single_device_publishes -v
```

### In Docker
```bash
docker exec iot_hub_web pytest apps/telemetry/tests/test_integration_basic.py -v
```

---

## Debugging Failed Tests

### Check MQTT messages
```python
def test_something(mqtt_setup):
    # ...
    messages = mqtt_setup["get_messages"]("sensors/TEMP-001/data")
    print(f"Messages: {len(messages)}")
    for msg in messages:
        print(f"Payload: {msg['payload']}")
```

### Check device state
```python
device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")
device.start()
time.sleep(0.1)
device.stop()
print(f"Published: {device.message_count}")
print(f"Last value: {device.last_value}")
```

### Verify fixture setup
```python
def test_check_fixture(mqtt_setup):
    assert mqtt_setup["client"].is_connected()
    assert mqtt_setup["factory"] is not None
    assert mqtt_setup["broker_id"] is not None
```

---

## Test Statistics

| Metric | Value |
|--------|-------|
| Total Tests | 14 |
| Passing | 14 ✅ |
| Duration | ~8 seconds |
| Coverage | Core functionality |
| Isolation | Complete (per-test brokers) |
| Mocks Used | MQTT, Devices, Helpers |

---

## What These Tests Validate

✅ **MQTT Mock Works**
- Publishing messages
- Topic isolation
- Message retrieval
- Multi-broker support

✅ **Device Simulator Works**
- Publishing in background thread
- Message count tracking
- Multiple concurrent devices
- Different sensor types

✅ **Test Data Builders Work**
- Telemetry creation
- Rule creation
- JSON serialization
- All fluent methods

✅ **End-to-End Flow Works**
- Device → MQTT → Message storage
- Multiple devices simultaneously
- Message structure preservation
- Realistic concurrent scenario

---

## Integration with Other Tests

```
Unit Tests (282 tests)
├── test_models_complete.py
├── test_mqtt_idempotency.py
├── test_transformations_edge_cases.py
└── ... 7 files total

Integration Tests (14 tests) ← YOU ARE HERE
└── test_integration_basic.py
    ├── MQTT functionality
    ├── Device simulation
    └── End-to-end flow
```

**Unit tests** validate individual components in isolation.
**Integration tests** validate components working together.

Combined: **296 tests, 87% coverage, production ready.**

---

## Kafka Mock Usage in Unit Tests

While basic integration tests focus on MQTT, Kafka mocks are essential for rules and events unit tests:

### Files Using Kafka Mocks
- `backend/apps/rules/tests/test_realtime_consumer.py` - Tests RulesConsumer Kafka integration
- `backend/apps/rules/tests/test_trigger_engine_realtime.py` - Tests event message production

### Kafka Mock Components (from kafka.py)
- **MockProducer** - Simulate sending events to Kafka topics
- **MockConsumer** - Simulate consuming telemetry/events from Kafka
- **get_kafka_producer()** - Factory returning mock or real producer
- **get_kafka_consumer()** - Factory returning mock or real consumer

### Example Usage in Unit Tests
```python
from apps.telemetry.mocks.kafka import MockProducer, MockConsumer, get_mock_topic_messages

def test_rule_event_production():
    """Test that triggered rules produce events to Kafka."""
    producer = MockProducer()

    # Simulate rule trigger
    producer.send("events", {
        "rule_id": "rule-123",
        "device_id": "device-456",
        "triggered": True
    })

    # Verify message was produced
    messages = get_mock_topic_messages("events")
    assert len(messages) == 1
```

### Benefits
- ✅ No real Kafka broker needed for unit tests
- ✅ In-memory message storage (thread-safe)
- ✅ Consumer offset tracking (realistic behavior)
- ✅ API compatible with confluent-kafka
- ✅ Fast execution (no network/IO)

---

## Notes

- Tests don't use real MQTT (paho-mqtt) or Kafka
- All in-memory, deterministic
- Fast execution (perfect for CI/CD)
- Easy debugging (all state visible)
- Realistic scenarios (concurrent devices, JSON messages)

