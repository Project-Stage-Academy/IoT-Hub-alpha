# Mock Infrastructure

Mock modules for testing IoT Hub integration without real MQTT brokers and Kafka.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         Mocking Infrastructure                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  MQTT Mock (mqtt.py)                         │  │
│  │  - MockMQTTClient: MQTT client without paho │  │
│  │  - MockBroker: In-memory message store      │  │
│  │  - MockMQTTMessage: MQTT message interface  │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Device Simulator (devices.py)               │  │
│  │  - VirtualDevice: IoT device w/ background  │  │
│  │  - VirtualDeviceFactory: Create sensors    │  │
│  │  - VirtualDeviceStatus: Online/offline      │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Time Control (time.py)                      │  │
│  │  - MockClock: Control time without sleep()  │  │
│  │  - TimeFreeze: Context manager               │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Test Helpers (helpers.py)                   │  │
│  │  - TelemetryBuilder: Fluent API for data    │  │
│  │  - RuleBuilder: Fluent API for rules        │  │
│  │  - Random generators: Serials, IDs          │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 1. MQTT Mock (mqtt.py)

### MockMQTTClient

Replacement for `paho.mqtt.client.Client` without real MQTT broker.

**Methods:**
- `connect(host, port)` - Connection (no-op, always succeeds)
- `publish(topic, payload, qos, retain)` - Publish to in-memory broker
- `subscribe(topic, qos)` - Subscribe to topic
- `set_on_message(callback)` - Register callback function
- `is_connected()` - Connection status

**Example:**
```python
client = MockMQTTClient(client_id="sensor-001", broker_id="test-broker")
client.connect("localhost", 1883)
client.publish("sensors/temp/data", b'{"value": 25.5}')
messages = client.get_published_messages("sensors/temp/data")
assert len(messages) == 1
```

### MockBroker

In-memory message storage with thread-safe access.

**Benefits:**
- Local storage (no Docker/Kafka needed)
- Multi-broker isolation (for test isolation)
- Instant operations (no network delay)

**Data structure:**
```python
_brokers = {
    "broker-1": {
        "sensors/temp": [
            {"payload": b"...", "qos": 1, "timestamp": 1234.5}
        ]
    }
}
```

---

## 2. Device Simulator (devices.py)

### VirtualDevice

Simulates real IoT device with background publishing thread.

**Parameters:**
```python
device = VirtualDevice(
    serial_number="TEMP-SN-001",
    device_type="temperature_sensor",
    mqtt_client=client,
    publish_interval=0.5,  # seconds between publishes
    measurement_fn=lambda: random.uniform(20, 30)  # value generator
)
```

**Methods:**
- `start()` - Start publishing in background thread
- `stop()` - Stop publishing
- `get_last_value()` - Last published value
- `message_count` - Number of published messages

**Message format:**
```json
{
  "serial_number": "TEMP-SN-001",
  "device_type": "temperature_sensor",
  "value": 25.5,
  "timestamp": "2026-03-01T12:00:00.123456Z",
  "schema_version": "1.0"
}
```

### VirtualDeviceFactory

Factory for quick creation of different sensor types.

```python
factory = VirtualDeviceFactory(mqtt_client)

# Individual sensors
temp = factory.create_temperature_sensor("TEMP-001")
vibr = factory.create_vibration_sensor("VIB-001")
curr = factory.create_current_sensor("CURR-001")
pres = factory.create_pressure_sensor("PRES-001")
humi = factory.create_humidity_sensor("HUM-001")

# Device group
devices = factory.create_device_group(
    count=5,
    device_type="temperature_sensor",
    serial_prefix="TEMP"
)
```

### VirtualDeviceStatus

Manage online/offline status for devices.

```python
status = VirtualDeviceStatus(mqtt_client)
status.set_online("TEMP-001")   # Publish "devices/TEMP-001/status" → "online"
status.set_offline("TEMP-001")  # Publish "devices/TEMP-001/status" → "offline"
```

---

## 3. Kafka Mock (kafka.py)

### MockProducer

Mock Kafka Producer for unit testing without real broker.

**Methods:**
- `send(topic, value, key=None)` - Produce message to topic
- `flush()` - Flush pending messages (no-op)
- `close()` - Close producer (no-op)

**Example:**
```python
producer = MockProducer()
producer.send("events", {"rule_id": "123", "triggered": True})
producer.flush()

messages = get_mock_topic_messages("events")
assert len(messages) == 1
```

### MockConsumer

Mock Kafka Consumer for unit testing.

**Methods:**
- `subscribe(topics)` - Subscribe to topics list
- `poll(timeout_ms=1000)` - Poll for next message
- `close()` - Close consumer

**Example:**
```python
consumer = MockConsumer({"group.id": "test-group"})
consumer.subscribe(["events"])

msg = consumer.poll(1000)
if msg:
    data = json.loads(msg.value().decode("utf-8"))
    print(data)
```

### Factory Functions

```python
# Get real or mock producer (based on confluent-kafka availability)
producer = get_kafka_producer(
    bootstrap_servers="kafka:9092",
    default_topic="my_topic"
)

# Get real or mock consumer
consumer = get_kafka_consumer(
    bootstrap_servers="kafka:9092",
    group_id="my-group",
    auto_offset_reset="earliest"
)
```

**Benefits:**
- No real Kafka needed for unit tests
- In-memory message store (thread-safe)
- Fast execution
- Consumer offset tracking
- API compatible with confluent-kafka

---

## 4. Time Control (time.py)

### MockClock

Control time without using `time.sleep()`.

**Methods:**
```python
clock = MockClock()  # Default: 2026-03-01 12:00:00

clock.set_time("2026-03-01 15:00:00")  # Set time
clock.advance(3600)                     # Add seconds
clock.advance_minutes(30)               # Add minutes
clock.advance_hours(2)                  # Add hours
clock.advance_days(1)                   # Add days

current = clock.current_time()          # Get current datetime
```

**Time comparisons:**
```python
clock.is_past(some_datetime)            # Has this time passed?
clock.is_future(some_datetime)          # Is this time in future?
seconds = clock.time_until(some_datetime)  # Seconds until time?
```

### TimeFreeze

Context manager for global time control.

```python
with TimeFreeze("2026-03-01 12:00:00") as clock:
    clock.advance_hours(1)
    # Inside: time = 13:00
    # Outside: time restored
```

---

## 5. Test Helpers (helpers.py)

### TelemetryBuilder

Fluent API for creating test telemetry data.

```python
telemetry = (
    TelemetryBuilder()
    .with_serial("TEMP-001")
    .with_value(25.5)
    .with_device_type("temperature_sensor")
    .with_schema_version("1.0")
    .with_timestamp("2026-03-01T12:00:00Z")
    .with_fields({"location": "Warehouse A"})
    .build()  # Returns dict
)

json_str = TelemetryBuilder().build_json()      # JSON string
json_bytes = TelemetryBuilder().build_bytes()   # JSON bytes
```

### RuleBuilder

Fluent API for creating test rules.

```python
rule = (
    RuleBuilder()
    .with_name("High Temperature Alert")
    .with_threshold(30.0)
    .with_operator("gt")  # gt, gte, lt, lte, eq, ne
    .with_window_seconds(300)
    .with_occurrences(2)
    .build()
)
```

### Random Generators

```python
serial = random_serial_number()          # "SN-ABC123"
device_id = random_device_id()           # UUID
value = random_telemetry_value(0, 100)  # Float 0-100
timestamp = random_timestamp()           # ISO 8601 string
```

---

## Pytest Fixtures (conftest.py)

### Core fixtures

```python
@pytest.fixture
def mqtt_broker():
    """Isolated MQTT broker for test."""
    broker_id = f"test-{random_serial_number()}"
    yield broker_id

@pytest.fixture
def mqtt_client(mqtt_broker):
    """Pre-configured MQTT client."""
    client = MockMQTTClient(client_id="test-client", broker_id=mqtt_broker)
    client.connect("localhost", 1883)
    yield client
    client.disconnect()

@pytest.fixture
def mqtt_setup(mqtt_client, mqtt_broker):
    """Complete MQTT infrastructure."""
    factory = VirtualDeviceFactory(mqtt_client)
    status = VirtualDeviceStatus(mqtt_client)

    def get_messages(topic=None):
        return get_mock_broker_messages(mqtt_broker, topic)

    yield {
        "client": mqtt_client,
        "factory": factory,
        "status": status,
        "broker_id": mqtt_broker,
        "get_messages": get_messages,
    }
```

### Time fixtures

```python
@pytest.fixture
def clock():
    """Time control for test."""
    mock_clock = MockClock()
    yield mock_clock
    mock_clock.reset()

@pytest.fixture
def frozen_time():
    """Context manager for time freeze."""
    return TimeFreeze
```

---

## Usage Examples

### Simple test

```python
def test_device_publishes_data(mqtt_setup):
    # Setup
    device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")

    # Publish
    device.start()
    time.sleep(0.2)  # Allow messages to publish
    device.stop()

    # Verify
    messages = mqtt_setup["get_messages"]("sensors/TEMP-001/data")
    assert len(messages) > 0

    payload = json.loads(messages[0]["payload"])
    assert payload["serial_number"] == "TEMP-001"
    assert payload["device_type"] == "temperature_sensor"
```

### Time control test

```python
def test_rule_window(clock):
    clock.set_time("2026-03-01 12:00:00")

    # Do something at specific time
    clock.advance_minutes(5)
    assert clock.current_time().minute == 5

    clock.advance_hours(1)
    assert clock.current_time().hour == 13
```

### Multi-device test

```python
def test_many_devices(mqtt_setup):
    devices = mqtt_setup["factory"].create_device_group(
        count=5,
        device_type="temperature_sensor"
    )

    for device in devices:
        device.start()

    time.sleep(0.3)

    for device in devices:
        device.stop()
        assert device.message_count > 0
```

---

## Thread Safety

All mock components are thread-safe:

- **MockBroker**: Uses `_brokers_lock` for synchronization
- **VirtualDevice**: Publishes in background thread safely
- **MockClock**: No locking needed (synchronous)
- **MockProducer/Consumer**: Uses `_topics_lock` for Kafka topic access

```python
# Safe even with parallel publishing
for device in devices:
    device.start()  # Background threads
# All synchronized through broker
```

---

## Benefits of Mock Infrastructure

✅ **Speed** - Millions of tests in seconds (local, no network)
✅ **Isolation** - Each test independent (separate brokers)
✅ **Deterministic** - No network delays, OS timing
✅ **Simple** - No Docker/Kafka needed for unit tests
✅ **Debuggable** - All state in memory, easy to inspect

---

## Files

```
backend/apps/telemetry/mocks/
├── __init__.py              # Export all mock components
├── mqtt.py                  # MockMQTTClient, MockBroker
├── devices.py               # VirtualDevice, Factory
├── time.py                  # MockClock, TimeFreeze
├── kafka.py                 # MockProducer, MockConsumer
└── helpers.py               # Builders, random generators
```
