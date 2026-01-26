# MVP Security Plan

This document outlines the security goals, threat model, and scope of protections for the IoT Hub application during its Minimum Viable Product (MVP) phase.

## 1. MVP Security Goals

The primary security goals for the MVP are focused on establishing a secure foundation for the platform's core functionality.

- **Confidentiality**: Ensure that only authorized users and systems can access API endpoints and data.
- **Integrity**: Protect telemetry and device data from unauthorized modification, ensuring that data ingested from devices is the same data stored and processed.
- **Availability**: Ensure the API and data ingestion endpoints remain available for legitimate users and devices, protected against basic denial-of-service vectors.
- **Traceability**: Log significant security-related events, such as authentication attempts and administrative actions, to enable auditing.

## 2. Threat Model & Assumptions

For the MVP, we assume a semi-trusted environment and prioritize threats that are most likely to be encountered by a web-based API platform.

### In-Scope Threats

- **Unauthorized API Access**: An external actor attempts to access or manipulate data (devices, rules, events) without proper authentication.
  - *Mitigation*: API endpoints are protected by JWT-based Bearer Token authentication.
- **Data Tampering in Transit**: An attacker on the same network attempts to intercept and modify API requests.
  - *Mitigation*: TLS is enforced on the API gateway/proxy in staging and production environments to encrypt all traffic. A local TLS workflow is provided for development.
- **Insecure Direct Object Reference (IDOR)**: An authenticated user attempts to access resources (e.g., another user's device) they are not authorized to view by guessing sequential IDs.
  - *Mitigation*: Backend logic must enforce ownership checks, ensuring users can only access resources associated with their account. (Note: This is a design goal for the API implementation).
- **Credential Leakage**: Developer credentials or application secrets are accidentally exposed.
  - *Mitigation*: Secrets are managed via environment variables (`.env` file) and are explicitly excluded from source control via `.gitignore`.

### Out-of-Scope Threats for MVP

- **Advanced Denial-of-Service (DDoS) Attacks**: Large-scale, coordinated attacks aimed at overwhelming the service.
- **Physical Device Security**: Tampering with or compromising the IoT devices themselves. We assume devices operate in a physically secure environment.
- **Advanced Persistent Threats (APTs)**: Sophisticated, long-term attacks by well-funded actors.
- **Internal Threats**: Malicious actions performed by authenticated users with legitimate access (e.g., an administrator intentionally causing harm).

## 3. Scope of Protections by Environment

Security measures are applied differently across environments to balance security with ease of development.

### Development (`local`)

The development environment is optimized for rapid iteration and debugging.

- **Authentication**: JWT authentication is in place, but developers may use a "fake" token endpoint or simplified user accounts for ease of use.
- **Encryption**: HTTPS is available via a locally-trusted development certificate (`mkcert`) through the Nginx proxy service. This protects against casual network sniffing but is not production-grade.
- **Secrets**: Managed in a local `.env` file. The default values in `.env.example` are sufficient to run the stack but should not be used elsewhere.
- **Network Access**: Services are exposed on `localhost`. There is no restriction on network access.

### Staging

The staging environment should mirror the production setup as closely as possible to provide a realistic testing ground.

- **Authentication**: Uses the same authentication provider and logic as production. Test users should have realistic, segregated permissions.
- **Encryption**: TLS is mandatory and should be terminated at a production-grade ingress controller or load balancer using a valid certificate from a trusted CA (e.g., Let's Encrypt).
- **Secrets**: All secrets (database passwords, Django `SECRET_KEY`, JWT signing keys) **must** be unique, strong, and securely managed via a proper secrets management system (e.g., environment variables injected by the CI/CD platform, HashiCorp Vault, AWS Secrets Manager).
- **Network Access**: Access to the staging environment should be restricted. At a minimum, administrative endpoints (like the Django Admin) should be firewalled to specific IP addresses (e.g., the office VPN).
- **Auditing**: Logging levels should be increased to capture all relevant access and error events for security monitoring.
