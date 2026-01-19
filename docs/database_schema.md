# Database Schema — IoT Catalog Hub (MVP)

This document describes the core database schema for the IoT Hub MVP monolith.
The schema focuses on device registration, telemetry ingestion, rule evaluation,
event generation, and notification delivery.

PostgreSQL is used as the primary database.

---

## 1. Device Types

**Purpose:**  
Defines reusable types of IoT devices (e.g. vibration sensors, temperature sensors).

**Table:** `device_types`

**Main fields:**
- `id` (UUID, PK) — unique identifier
- `name` (varchar, unique) — device type name (`vibration_sensor`, `temperature_sensor`)
- `description` (text) — optional description
- `default_metrics` (jsonb) — default metric names and units
- `created_at` (timestamp)

**Indexes:**
- unique index on `name`

---

## 2. Devices

**Purpose:**  
Represents physical IoT devices installed on machines.

**Table:** `devices`

**Main fields:**
- `id` (UUID, PK)
- `device_type_id` (FK → device_types.id)
- `name` (varchar) — human-readable name
- `serial_number` (varchar, unique)
- `location` (text) — machine or shop floor location
- `status` (enum) — active / inactive / error
- `created_at` (timestamp)
- `updated_at` (timestamp)

**Indexes:**
- unique index on `serial_number`
- index on `device_type_id`
- index on `status`

---

## 3. Telemetry

**Purpose:**  
Stores time-series measurements received from devices.

**Table:** `telemetry`

**Main fields:**
- `id` (bigserial, PK)
- `device_id` (FK → devices.id)
- `timestamp` (timestamp)
- `value` (numeric)
- `unit` (enum) — mm/s, celsius, kWh

**Notes:**
- This table is expected to grow quickly.
- In later stages it may be migrated to TimescaleDB.

**Indexes:**
- composite index on `(device_id, timestamp)`
- index on `timestamp`

---

## 4. Rules

**Purpose:**  
Defines business rules that evaluate telemetry data and trigger actions.

**Table:** `rules`

**Main fields:**
- `id` (UUID, PK)
- `device_id` (FK → devices.id, nullable)
- `metric_name` (varchar) — vibration, temperature, power
- `operator` (enum) — >, <, >=, <=, =
- `threshold` (numeric)
- `action_type` (enum) — alert, stop_machine, maintenance
- `is_enabled` (boolean)
- `created_at` (timestamp)

**Indexes:**
- index on `(device_id, is_enabled)`
- index on `metric_name`

---

## 5. Events

**Purpose:**  
Stores facts of rule execution when a condition is met.

**Table:** `events`

**Main fields:**
- `id` (bigserial, PK)
- `rule_id` (FK → rules.id)
- `device_id` (FK → devices.id)
- `telemetry_id` (FK → telemetry.id)
- `timestamp` (timestamp)
- `severity` (enum) — critical, warning, info
- `message` (text)
- `status` (enum) — new, acknowledged, resolved

**Indexes:**
- composite index on `(device_id, timestamp)`
- index on `status`
- index on `severity`

---

## Notes

Enum types are represented either as PostgreSQL ENUMs or Django model choices,
depending on migration strategy.

- User authentication is handled by Django’s built-in User model in the MVP.
- Notification delivery is out of scope for the MVP and may be added later.
- The schema is expected to evolve during the microservice split phase.
