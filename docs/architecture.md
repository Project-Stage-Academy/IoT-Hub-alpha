# Architecture — Monolithic MVP

This document describes the architecture of the IoT Hub **monolithic MVP**.  

---

## 1. High-level Architecture Overview

The IoT Hub MVP provides a backend platform for:
- registering and managing IoT devices,
- ingesting telemetry data from sensors,
- evaluating rules based on telemetry values,
- generating events and tracking notification attempts.

All core functionality is implemented inside a single Django service.  
Redis, Prometheus, and a message broker are **planned integrations** and are documented to ensure
future architectural continuity.

---

## 2. Implemented Components

### 2.1 Backend (`backend`)
**Type:** Django Monolith  
**Technology:** Python 3.13, Django 5.2 

**Responsibilities:**
- Expose REST API under `/api/v1/...`
- Provide telemetry ingest endpoint (unauthenticated, per API rules)
- Handle JWT-based authentication for protected endpoints
- Manage devices, device types, rules, events, and notifications
- Evaluate rules and generate events
- Provide administrative interface via Django Admin (`/admin/`)
- Run database migrations on startup (dev environment)

---

### 2.2 Database (`db`)
**Type:** PostgreSQL 15  

**Responsibilities:**
- Persist domain data:
  - users
  - device_types
  - devices
  - telemetry
  - rules
  - events
  - notifications
- Store telemetry data in time-series friendly structures
- Enforce relational integrity using foreign keys

**Notes:**
- UUIDs are used for identifiers where applicable
- TimescaleDB extension is planned for telemetry optimization

---


## 3. MVP Architecture Diagram (Mermaid)


---


## 4. Data Flows
4.1 Device Registration Flow

1. Admin creates a device type with default metrics
2. Admin or operator registers a device linked to a device type
3. Device becomes available for telemetry ingestion

Storage:
`device_types`, `devices tables` in PostgreSQL

---

4.2 Telemetry Ingestion Flow

1. Device sends telemetry to ingest endpoint (REST/JSON)
2. Backend validates device identifier and payload format
3. Telemetry is persisted in the database
4. Associated rules are evaluated

Storage:
`telemetry` table (timestamp + JSONB metrics)

---

4.3 Rule Evaluation and Event Generation Flow
1. Backend loads active rules for the device and metric
2. Threshold comparison is applied (gt, lt, gte, lte, eq, neq)
3. On match, an event is created with severity and context
4. Notification attempts are recorded

Storage:
`rules`, `events`, `notifications` tables

Planned:
Events will be published to the message broker for downstream consumers.
