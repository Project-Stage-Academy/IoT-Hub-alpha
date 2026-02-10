# API Change Process

This document defines how we evolve the API safely using explicit versioning and a standard deprecation pattern.
The goal is to ensure breaking changes are never introduced silently.

---

## Scope

This process applies to:

- `docs/api.yaml` (OpenAPI spec)
- Generated artifacts (Postman collection, mock server behavior)
- Any client-facing API behavior (paths, payloads, auth, semantics)

---

## Definitions

### Breaking change

A change is **breaking** if it can cause an existing client to fail without code changes. Examples:

- Removing or renaming an endpoint, field, enum value
- Changing a field type (string → number), format, or required/optional status
- Changing auth requirements (public → auth required)
- Changing response status codes or response schema
- Tightening validation that previously accepted requests

### Non-breaking change

A change is typically **non-breaking** if it only adds capabilities:

- Adding a new endpoint
- Adding an optional field
- Adding a new response header (non-required)
- Adding a new enum value **only if** clients treat enums as open sets (otherwise treat as breaking)

> When in doubt, treat as breaking and follow the deprecation process.

---

## Versioning guidance

We use **explicit API versions** and keep older versions available during a deprecation window.

### Where the version lives

- **Path versioning**: `/v1/...`, `/v2/...`

1) Deprecating an operation (endpoint)

Mark the operation as deprecated and include a clear timeline and replacement.

```yaml
paths:
  /rules/{id}:
    patch:
      deprecated: true
      summary: Update rule (deprecated)
      description: |
        **Deprecated:** 2026-02-10  
        **Removal (earliest):** 2026-05-10  
        **Replacement:** `PATCH /v2/rules/{id}`

        Migration notes:
        - Field `condition` was replaced by `conditions[]`
        - Response now returns `rule` envelope
      x-deprecation:
        deprecated_since: "2026-02-10"
        removal_not_before: "2026-05-10"
        replaced_by: "/v2/rules/{id}"
        migration_guide: "docs/migrations/rules-v2.md"
```
Rules:

- deprecated: true is required.
- description must include: deprecated date, removal date, replacement.
- x-deprecation is required for machine-readability.

Examples
Example: breaking change done correctly

- Add /v2/rules/...
- Mark /v1/rules/... as deprecated with dates and replacement
- Provide migration notes
- Keep both during the deprecation window


## Schema Versioning

Schema_version is present on the following endpoints:

- telemetry

schema_versioned endpoins use schema_version which is passed in the body of the request:
```json
schema_version: "1.0"
```

Each schema version has its own structure that must be followed, 

any new schema must be documented.