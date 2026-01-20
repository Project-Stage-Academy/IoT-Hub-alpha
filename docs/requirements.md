# Requirements — Monolithic MVP

## 1. Overview

This document defines the functional and non-functional requirements for the IoT Hub **monolithic MVP**.
The purpose of this document is to establish a clear and shared understanding of the system scope, constraints,
and acceptance criteria during the internship phase.

The MVP focuses on providing a single-node, containerized backend capable of managing IoT devices,
ingesting telemetry data, applying basic rules, and persisting events for further processing.

---

## 2. User Roles

The system supports the following user roles:

### 2.1 Admin
- Full access to all system features
- Manage users, devices, device types, rules, and system configuration
- Access Django Admin interface
- Perform operational tasks (maintenance, migrations, inspections)

### 2.2 Operator
- Manage devices and view telemetry data
- Monitor events and triggered rules
- Acknowledge and resolve operational events
- No access to user or system-level configuration

### 2.3 Viewer
- Read-only access to devices, telemetry, and events
- Cannot modify system state
- Intended for monitoring and reporting purposes

---

## 3. Functional Requirements

### 3.1 Device Management
- The system MUST allow creation, update, and deletion of IoT devices
- Each device MUST be associated with a device type
- Each device MUST have a unique identifier (UUID)
- Device metadata (name, serial number, location, status) MUST be persisted in the database

### 3.2 Telemetry Ingestion
- The system MUST provide an ingest API for receiving telemetry data
- Telemetry data MUST be accepted in JSON format
- Telemetry ingest endpoint MUST accept unauthenticated requests
- Each telemetry record MUST be associated with a device via its identifier
- Telemetry timestamps MUST use ISO 8601 format in UTC

### 3.3 Telemetry Storage
- Telemetry data MUST be stored in PostgreSQL using time-series optimized structures
- The system MUST support querying telemetry by device and time range
- Telemetry metrics MUST support flexible schemas using JSONB

### 3.4 Rules and Events
- The system MUST support defining rules based on telemetry metrics
- Rules MUST support comparison operators (gt, lt, gte, lte, eq, neq)
- When a rule condition is met, the system MUST generate an event
- Events MUST include severity, message, timestamp, and triggering values
- Events MUST be persisted in the database

### 3.5 Notifications
- The system MUST record notification attempts linked to events
- Notification delivery MAY be simulated or stored without external integrations
- Real external notification delivery (email/SMS/webhooks) is not required for MVP

### 3.6 API Standards
- The API MUST follow REST and JSON conventions
- The API MUST be versioned using `/api/v1/`
- Field naming MUST use `snake_case`
- Collection endpoints MUST support pagination
- Error responses MUST follow a standard error format

### 3.7 Authentication and Authorization
- Authenticated API endpoints MUST use JWT-based authentication
- Telemetry ingest endpoint MUST not require authentication
- Authorization rules are role-based but limited in MVP scope

---

## 4. Non-Functional Requirements

### 4.1 Performance
- The system is designed for low to moderate load suitable for an internship MVP
- Expected scale:
  - Up to 100 registered devices
  - Telemetry ingestion up to ~1 message per second per device
- API responses for standard read operations SHOULD complete within 500 ms under nominal load

### 4.2 Data Retention
- Telemetry data MUST be retained for a configurable period
- Default telemetry retention period is 90 days
- Older telemetry data MAY be automatically compressed or removed

### 4.3 Availability
- The MVP MUST support best-effort availability
- The system is deployed as a single-node application
- No high-availability or failover guarantees are provided

### 4.4 Reliability
- The system MUST persist all accepted telemetry data before acknowledging ingestion
- Database integrity MUST be enforced using foreign keys and constraints

### 4.5 Security
- All external API access MUST be served over TLS
- Secrets MUST be provided via environment variables
- No secrets MUST be committed to version control
- Audit logging is out of scope for the MVP

---

## 5. Technical Constraints

- Backend: Python 3.13, Django 6.0.1
- Database: PostgreSQL 15
- Time-series optimization: TimescaleDB extension
- UUID generation: UUID-OSSP extension
- ORM: Django ORM
- Connection pooling: psycopg2-binary with pooling enabled
- Orchestration: Docker and Docker Compose
- Deployment targets: local and staging environments only
- Documentation format: Markdown and DBML

---

## 6. Out of Scope for MVP

The following features are explicitly excluded from the monolithic MVP:

- End-user UI beyond Django Admin
- Real-time dashboards
- High availability and horizontal scaling
- Production-grade security hardening
- External alert delivery (email, SMS, third-party services)
- Full RBAC permission matrix enforcement
- Multi-region or cloud-native deployments

---

## 7. Acceptance Criteria

The monolithic MVP is considered complete when all of the following criteria are met:

1. The project can be started using:
   ```bash
   docker compose up -d --build
