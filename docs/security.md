# Security — Monolithic MVP (Initial Decisions)

This document records the initial security decisions for the monolithic MVP.

## TLS (External Endpoints)
- **Staging/demo/prod-like environments:** external HTTP endpoints **MUST** be served over **TLS**.
- **Local development:** plain HTTP is acceptable.
- TLS termination is handled by a reverse proxy / ingress (outside the app containers). Internal Docker network traffic is not TLS-protected in MVP.

## Authentication (JWT)
- API uses **JWT**:
  - Authorization: `Bearer <token>`
  - Access token: **60 min**
  - Refresh token: **10 days**

## Telemetry Ingest Endpoint

- The telemetry ingest endpoint does NOT require authentication.
- Device identity is validated using a dedicated HTTP header:
  `X-Device-SSN`.
- The backend MUST validate that the provided SSN exists in the `devices`
  table before processing the request body.
- Requests with a missing or unknown `X-Device-SSN` MUST be rejected
  before telemetry parsing or persistence.
- The SSN is NOT required to be present in the request body and MUST NOT
  be used as a source of device identity.

## Secrets Handling

### Docker Compose
- Secrets are provided via environment variables loaded from `.env`.
- `.env` **MUST NOT** be committed to version control.
- `.env.example` documents required variables without exposing secrets.

### CI (GitHub Actions)
- Secrets **MUST** be stored in GitHub Actions Secrets.
- Secrets are injected into workflows as environment variables.
- Secrets **MUST NOT** be hardcoded in workflow files or logs.

## Internal APT Repository Access
- The internal APT repository is a restricted resource.
- Access is limited to CI pipelines and authorized infrastructure nodes.
- Authentication is enforced using credentials or SSH keys stored as CI secrets.
- APT repository credentials **MUST NOT** be committed to the repository.
