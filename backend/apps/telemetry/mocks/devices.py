"""
Virtual MQTT device simulator for integration testing.
Simulates real IoT devices publishing telemetry to MQTT broker.
"""

import json
import logging
import random
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger("telemetry.mock_devices")


class VirtualDevice:
    """
    Simulates real IoT device publishing MQTT messages.

    Runs in separate thread to simulate real device behavior.
    Publishes messages at configurable interval with measurement function.

    Attributes:
        serial_number: Device identifier (e.g., "TEMP-SN-001")
        device_type: Type of device (temperature, vibration, etc.)
        mqtt_client: MQTT client for publishing
        publish_interval: Seconds between publishes
        measurement_fn: Callable that returns telemetry value
        status_fn: Callable that returns device status ("online" / "offline")
        _thread: Background publishing thread
        _running: Flag to control publishing loop
        _message_count: Count of published messages
        _last_value: Last published value

    Usage:
        def measure_temperature():
            return 25.5 + random.uniform(-0.5, 0.5)

        device = VirtualDevice(
            serial_number="TEMP-SN-001",
            device_type="temperature_sensor",
            measurement_fn=measure_temperature,
            publish_interval=1.0
        )
        device.start()
        # ... run tests ...
        device.stop()
        assert device.message_count > 5
    """

    def __init__(
        self,
        serial_number: str,
        device_type: str,
        mqtt_client: Any,
        measurement_fn: Optional[Callable] = None,
        status_fn: Optional[Callable] = None,
        publish_interval: float = 1.0,
    ):
        self.serial_number = serial_number
        self.device_type = device_type
        self.mqtt_client = mqtt_client
        self.publish_interval = publish_interval

        def _default_measurement():
            return random.uniform(0, 100)

        self.measurement_fn = measurement_fn or _default_measurement
        self.status_fn = status_fn or (lambda: "online")
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._message_count = 0
        self._last_value: Optional[float] = None
        logger.info(f"VirtualDevice created: {serial_number} ({device_type})")

    def start(self) -> None:
        """Start publishing messages in background thread."""
        if self._running:
            logger.warning(f"[{self.serial_number}] Already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._publish_loop, daemon=True)
        self._thread.start()
        logger.info(f"[{self.serial_number}] Publishing started")

    def stop(self) -> None:
        """Stop publishing messages and wait for thread to finish."""
        if not self._running:
            logger.warning(f"[{self.serial_number}] Not running")
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        msg = f"[{self.serial_number}] Stopped ({self._message_count} msgs)"
        logger.info(msg)

    def _publish_loop(self) -> None:
        """Internal thread function - publishes messages in loop."""
        topic = f"sensors/{self.serial_number}/data"

        while self._running:
            try:
                value = self.measurement_fn()
                self._last_value = value

                # Create telemetry payload
                payload = {
                    "serial_number": self.serial_number,
                    "device_type": self.device_type,
                    "value": value,
                    "timestamp": datetime.now().isoformat(),
                    "unit": self._get_unit_for_type(),
                }

                payload_bytes = json.dumps(payload).encode("utf-8")
                self.mqtt_client.publish(topic, payload_bytes)
                self._message_count += 1

                logger.debug(f"[{self.serial_number}] Published: {value}")

            except Exception as e:
                logger.error(f"[{self.serial_number}] Publish error: {e}")

            time.sleep(self.publish_interval)

    def _get_unit_for_type(self) -> str:
        """Get measurement unit based on device type."""
        units = {
            "temperature_sensor": "°C",
            "vibration_sensor": "Hz",
            "current_sensor": "A",
            "pressure_sensor": "Pa",
            "humidity_sensor": "%",
        }
        return units.get(self.device_type, "unit")

    def publish_status(self, status: str = "online") -> None:
        """Publish device status (online/offline)."""
        topic = f"devices/{self.serial_number}/status"
        self.mqtt_client.publish(topic, status.encode("utf-8"))
        logger.info(f"[{self.serial_number}] Status published: {status}")

    def publish_online(self) -> None:
        """Publish online status."""
        self.publish_status("online")

    def publish_offline(self) -> None:
        """Publish offline status."""
        self.publish_status("offline")

    @property
    def message_count(self) -> int:
        """Return count of published messages."""
        return self._message_count

    @property
    def last_value(self) -> Optional[float]:
        """Return last published value."""
        return self._last_value

    @property
    def is_running(self) -> bool:
        """Check if device is publishing."""
        return self._running


class VirtualDeviceFactory:
    """
    Factory for creating pre-configured virtual devices.

    Provides convenience methods for common device types with
    realistic measurement functions.

    Usage:
        factory = VirtualDeviceFactory(mqtt_client)
        temp = factory.create_temperature_sensor("TEMP-SN-001")
        vib = factory.create_vibration_sensor("VIB-SN-001")
        devices = factory.create_device_group(count=5,
                                             device_type="temperature")
    """

    def __init__(self, mqtt_client: Any):
        self.mqtt_client = mqtt_client

    def create_temperature_sensor(
        self,
        serial_number: str,
        min_temp: float = 15.0,
        max_temp: float = 35.0,
    ) -> VirtualDevice:
        """Create temperature sensor with realistic range."""

        def measure_temp():
            return random.uniform(min_temp, max_temp)

        return VirtualDevice(
            serial_number=serial_number,
            device_type="temperature_sensor",
            mqtt_client=self.mqtt_client,
            measurement_fn=measure_temp,
            publish_interval=1.0,
        )

    def create_vibration_sensor(
        self, serial_number: str, min_hz: float = 0.0, max_hz: float = 50.0
    ) -> VirtualDevice:
        """Create vibration sensor with realistic frequency range."""

        def measure_vibration():
            return random.uniform(min_hz, max_hz)

        return VirtualDevice(
            serial_number=serial_number,
            device_type="vibration_sensor",
            mqtt_client=self.mqtt_client,
            measurement_fn=measure_vibration,
            publish_interval=1.0,
        )

    def create_current_sensor(
        self, serial_number: str, min_amp: float = 0.0, max_amp: float = 250.0
    ) -> VirtualDevice:
        """Create current sensor with realistic range."""

        def measure_current():
            return random.uniform(min_amp, max_amp)

        return VirtualDevice(
            serial_number=serial_number,
            device_type="current_sensor",
            mqtt_client=self.mqtt_client,
            measurement_fn=measure_current,
            publish_interval=1.0,
        )

    def create_pressure_sensor(
        self,
        serial_number: str,
        min_pa: float = 90000.0,
        max_pa: float = 110000.0,
    ) -> VirtualDevice:
        """Create pressure sensor with realistic range."""

        def measure_pressure():
            return random.uniform(min_pa, max_pa)

        return VirtualDevice(
            serial_number=serial_number,
            device_type="pressure_sensor",
            mqtt_client=self.mqtt_client,
            measurement_fn=measure_pressure,
            publish_interval=1.0,
        )

    def create_humidity_sensor(
        self, serial_number: str, min_rh: float = 20.0, max_rh: float = 80.0
    ) -> VirtualDevice:
        """Create humidity sensor with realistic range."""

        def measure_humidity():
            return random.uniform(min_rh, max_rh)

        return VirtualDevice(
            serial_number=serial_number,
            device_type="humidity_sensor",
            mqtt_client=self.mqtt_client,
            measurement_fn=measure_humidity,
            publish_interval=1.0,
        )

    def create_device_group(
        self, count: int, device_type: str, serial_prefix: str = "SN"
    ) -> list:
        """Create multiple devices of same type."""
        devices = []
        for i in range(count):
            serial = f"{serial_prefix}-{device_type[0:3].upper()}-{i:03d}"

            if device_type == "temperature_sensor":
                device = self.create_temperature_sensor(serial)
            elif device_type == "vibration_sensor":
                device = self.create_vibration_sensor(serial)
            elif device_type == "current_sensor":
                device = self.create_current_sensor(serial)
            elif device_type == "pressure_sensor":
                device = self.create_pressure_sensor(serial)
            elif device_type == "humidity_sensor":
                device = self.create_humidity_sensor(serial)
            else:
                logger.warning(f"Unknown device type: {device_type}")
                continue

            devices.append(device)

        logger.info(f"Created {len(devices)} devices of type {device_type}")
        return devices


class VirtualDeviceStatus:
    """
    Manage device online/offline status transitions.

    Simulates realistic device status events (online/offline).
    Supports status toggling (flaky connection simulation).

    Usage:
        status = VirtualDeviceStatus(mqtt_client)
        status.set_online("TEMP-SN-001")
        # ... run tests ...
        status.set_offline("TEMP-SN-001")
    """

    def __init__(self, mqtt_client: Any):
        self.mqtt_client = mqtt_client
        self._device_statuses: dict = {}

    def set_online(self, device_serial: str) -> None:
        """Set device online."""
        self._device_statuses[device_serial] = "online"
        topic = f"devices/{device_serial}/status"
        self.mqtt_client.publish(topic, b"online")
        logger.info(f"[{device_serial}] Status: online")

    def set_offline(self, device_serial: str) -> None:
        """Set device offline."""
        self._device_statuses[device_serial] = "offline"
        topic = f"devices/{device_serial}/status"
        self.mqtt_client.publish(topic, b"offline")
        logger.info(f"[{device_serial}] Status: offline")

    def toggle_online(self, device_serial: str, interval_sec: float = 5.0) -> None:
        """Toggle online/offline status (flaky connection)."""

        def toggle_loop():
            while True:
                self.set_online(device_serial)
                time.sleep(interval_sec)
                self.set_offline(device_serial)
                time.sleep(interval_sec)

        thread = threading.Thread(target=toggle_loop, daemon=True)
        thread.start()

    def get_status(self, device_serial: str) -> str:
        """Get current status."""
        return self._device_statuses.get(device_serial, "unknown")
