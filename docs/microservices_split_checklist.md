# MVP to Microservices Split Checklist

This document defines the **criteria and preparation steps** required before splitting the
IoT Hub monolithic MVP into independent microservices.

---

## 1. API Contract Readiness

Before extracting any service, API contracts MUST be stable and explicit.

### Criteria
- [x] All public APIs are documented using **OpenAPI 3.x**
- [x] API versioning strategy is defined and enforced (`/api/v1`)
- [x] Request/response schemas are explicit and validated
- [x] Error formats are standardized across endpoints
- [x] Pagination, filtering, and sorting rules are consistent
- [ ] Breaking changes policy is defined

### Notes
The API contract becomes the primary integration boundary between services.
No service split should occur while API behavior is still changing frequently.

---

## 2. Service Boundary Definition

Clear ownership boundaries MUST be defined before extraction.

### Criteria
- [x] Candidate services are identified (e.g. devices, telemetry ingest, rules, notifications)
- [ ] Each service has a single, well-defined responsibility
- [ ] Data ownership per service is clearly defined
- [ ] Cross-service communication paths are documented

### Notes
The message broker is the preferred boundary for decoupling producers and consumers.

---

## 3. Database Ownership and Data Strategy

Database coupling is one of the highest risks during a split.

### Criteria
- [ ] **BLOCKER**:  Ownership of each table is assigned to a single service
- [ ] **BLOCKER**: Decision made:  shared database (temporary) vs database-per-service
- [ ] **BLOCKER**:  Cross-service data access is prohibited or explicitly documented
- [ ] **BLOCKER**: Read-only replicas or API-based access planned where needed

### Migration Strategy
- [ ] Schema changes are backward-compatible
- [ ] Data migrations can be executed without downtime (or with acceptable downtime)
- [ ] Rollback strategy for failed migrations is documented

---

## 4. Messaging and Asynchronous Communication

Event-driven communication must be prepared before splitting.

### Criteria
- [ ] Message broker selected (Kafka or RabbitMQ)
- [ ] Event schemas are versioned and documented
- [ ] Producers and consumers are clearly identified
- [ ] Retry and failure handling strategy is defined
- [ ] Dead-letter queue (DLQ) or equivalent is planned

---

## 5. CI/CD Readiness per Service

Each microservice MUST be independently buildable and testable.

### Criteria
- [ ] Separate CI pipeline per service
- [ ] Linting, tests, and build steps run independently
- [ ] Docker image build per service is defined
- [ ] CI pipelines do not depend on monolith internals
- [ ] Artifacts (images, packages) are versioned and traceable

---

## 6. Configuration and Secrets Management

Configuration MUST be externalized and service-specific.

### Criteria
- [ ] Environment-based configuration for each service
- [x] Secrets are managed via CI/CD secret stores
- [x] No secrets are committed to repositories
- [x] Configuration defaults are documented

---

## 7. Observability and Monitoring

Splitting services without observability increases operational risk.

### Criteria
- [ ] Metrics are exposed per service
- [ ] Prometheus scraping is configured or planned
- [ ] Logs include service identifiers and correlation IDs
- [ ] Basic health checks are implemented (`/health`)

---

## 8. Deployment and Runtime Strategy

The deployment model must support multiple independently deployed services.

### Criteria
- [ ] Docker images are built per service
- [ ] Docker Compose or orchestration supports multi-service setup
- [ ] Network policies between services are defined
- [ ] Service startup and dependency ordering is documented

---

## 9. Security and Access Control

Security boundaries MUST be revisited after splitting.

### Criteria
- [ ] Auth strategy between services is defined (JWT, mTLS, tokens)
- [ ] Internal vs external endpoints are clearly separated
- [ ] Least-privilege access is enforced for service-to-service calls

---

## 10. Operational Readiness

The team must be ready to operate multiple services.

### Criteria
- [ ] Runbooks exist per service
- [ ] Backup and restore procedures are validated
- [ ] On-call or ownership model is defined
- [ ] Incident response process is documented

---

## 11. Final Go / No-Go Decision

The monolith can be split only if:

- [ ] All critical criteria above are satisfied
- [ ] No single service requires frequent synchronous calls to others
- [ ] The team agrees on service ownership and operational responsibility
- [ ] Rollback plan exists if the split introduces instability

---

## 12. Testing Strategy
### Criteria
- [ ] Unit test coverage ≥80% for business logic in each candidate service
- [ ] Integration tests exist for all cross-service interactions
- [ ] Contract tests (Pact, Spring Cloud Contract) implemented between services
- [ ] End-to-end tests cover critical user journeys
- [ ] Performance tests establish baseline metrics before split
- [ ] Load testing confirms each service can handle expected traffic independently
### Validation
- [ ] Test suite runs in <5 minutes for fast feedback
- [ ] Tests can run in isolation per service
- [ ] Test data fixtures are reproducible
- [ ] Smoke tests exist for post-deployment validation

## Summary

This checklist MUST be reviewed and approved before starting any microservices extraction.
Its purpose is to reduce risk, preserve system stability, and ensure that the transition from
a monolith to microservices is **intentional, controlled, and observable**.

