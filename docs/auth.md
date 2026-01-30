# JWT Authentication Plan

This document describes a conceptual JWT-based authentication design for the IoT Hub API.

> ⚠️ Note:
> This is a documentation-only design stub for the MVP.
> JWT authentication is NOT implemented yet.
> The project does NOT rely on Django REST Framework.
> The final implementation may use a custom solution or a third-party library.

---

## 1. Token Issuance

Clients obtain JWT tokens by providing valid credentials to a dedicated authentication endpoint.

- **Endpoint**: `POST /api/v1/auth/token/`
- **Request Body**:
  ```json
  {
    "username": "user@example.com",
    "password": "user_password"
  }

  ```
- **Response Body**:
  ```json
  {
    "access": "<access_token>",
    "refresh": "<refresh_token>"
  }
  ```

This endpoint is public and does not require prior authentication.

## 2. Token Lifetime

This endpoint is public and does not require prior authentication.

- **Access Token**: Short-lived to reduce the risk of theft.
  - **Lifetime**: 15 minutes
- **Refresh Token**: Long-lived, stored securely by the client, and used to obtain new access tokens.
  - **Lifetime**: 7 days

## 3. Refresh Flow

When an access token expires, the client can use its refresh token to get a new access token without re-authenticating.

- **Endpoint**: `POST /api/v1/auth/token/refresh/`
- **Request Body**:
  ```json
  {
    "refresh": "<refresh_token>"
  }
  ```
- **Response Body**:
  ```json
  {
    "access": "<new_access_token>"
  }
  ```

Token lifetimes are intentionally short to reduce the impact of token leakage.

## 4. Minimal Claims Required

The JWT payload will contain the following claims:

- `user_id`: The unique identifier of the user.
- `exp`: (Expiration Time) The timestamp when the token will expire.
- `iat`: (Issued At) The timestamp when the token was issued.
- `jti`: (JWT ID) A unique identifier for the token.
- `token_type`: The type of token, either `access` or `refresh`.
- `roles`: A list of roles assigned to the user (e.g., `["admin", "viewer"]`).

## 5. Device Tokens

For device authentication:

- Tokens are issued per-device

- roles will contain only ["device"]

- Tokens MUST be bound to a specific device_id

 Device tokens are restricted to device-scoped endpoints only

## 6. Roles and Scopes

We will define a set of roles to control access to different parts of the API.

- **Admin**: Full access to all resources. Can perform any CRUD operation.
- **Operator**: Can manage devices, rules, and events. Can view telemetry and notifications. Cannot manage users or system-level settings.
- **Viewer**: Read-only access to view devices, telemetry, and events.
- **Device**: A special role for IoT devices to authenticate and send telemetry data. This role should only have permission to post to its own telemetry endpoint.

### 7. Endpoint to Role/Scope Mapping

| Endpoint | Method | Required Role(s) | Description |
|---|---|---|---|
| `/api/v1/auth/token/` | `POST` | (Public) | Obtain a new token pair. |
| `/api/v1/auth/token/refresh/`| `POST` | (Public, with refresh token) | Refresh an access token. |
| | | | |
| `/api/v1/devices/` | `GET` | Viewer, Operator, Admin | List all devices. |
| `/api/v1/devices/` | `POST` | Operator, Admin | Create a new device. |
| `/api/v1/devices/{id}/`| `GET` | Viewer, Operator, Admin | Get details of a specific device. |
| `/api/v1/devices/{id}/`| `PUT`, `PATCH` | Operator, Admin | Update a device. |
| `/api/v1/devices/{id}/`| `DELETE` | Admin | Delete a device. |
| | | | |
| `/api/v1/telemetry/` | `POST` | Device | Submit telemetry data from a device. |
| `/api/v1/devices/{id}/telemetry/` | `GET` | Viewer, Operator, Admin | List telemetry for a specific device. |
| | | | |
| `/api/v1/rules/` | `GET` | Viewer, Operator, Admin | List all rules. |
| `/api/v1/rules/` | `POST` | Operator, Admin | Create a new rule. |
| `/api/v1/rules/{id}/` | `PUT`, `PATCH` | Operator, Admin | Update a rule. |
| `/api/v1/rules/{id}/` | `DELETE` | Admin | Delete a rule. |
| | | | |
| `/api/v1/events/` | `GET` | Viewer, Operator, Admin | List all events. |
| `/api/v1/events/{id}/` | `GET` | Viewer, Operator, Admin | Get details of a specific event. |
| `/api/v1/events/{id}/acknowledge/` | `POST` | Operator, Admin | Acknowledge an event. |
| `/api/v1/events/{id}/resolve/` | `POST` | Operator, Admin | Resolve an event. |
| | | | |
| `/api/v1/notification_templates/` | `GET` | Operator, Admin | List notification templates. |
| `/api/v1/notification_templates/` | `POST` | Admin | Create a notification template. |

## 8. Reference JWT Configuration

The following example is provided for reference only.
It does NOT represent the current project configuration

```python
ACCESS_TOKEN_LIFETIME = 15 * 60
REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60

JWT_ALGORITHM = "HS256"
JWT_SIGNING_KEY = "<secret>"

```

This plan provides a secure and scalable authentication system for the IoT Hub.
