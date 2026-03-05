# WebSocket Authentication

This document describes the token-based authentication system for WebSocket connections to the telemetry endpoint.

## Overview

WebSocket connections to `/ws/telemetry/` require authentication via a token passed in the query string. The system uses middleware to validate tokens before the connection reaches the consumer.

## Authentication Flows

### Flow 1: Client connects WITHOUT token

```
Client                Nginx                    Middleware                         Consumer
   │                    │                          │                                  │
   ├── GET /ws/telemetry/ ─►│                      │                                  │
   │    Upgrade: websocket  │                      │                                  │
   │                    ├── Forward to web:8000 ──►│                                  │
   │                    │                          │                                  │
   │                    │                          ├── Parse query_string             │
   │                    │                          │   token = None                   │
   │                    │                          │                                  │
   │                    │                          ├── Log: "websocket.auth_failed"   │
   │                    │                          │   reason: "no_token"             │
   │                    │                          │                                  │
   │◄─────────────────────── websocket.connect ────┤                                  │
   │                    │                          │                                  │
   ├── websocket.connect ─────────────────────────►│ (while loop receives this)       │
   │                    │                          │                                  │
   │◄─────────────────────── websocket.accept ─────┤                                  │
   │◄─────────────────────── websocket.close ──────┤  code: 4001                      │
   │                    │                          │                                  │
   ✗ Connection closed  │                          │              Consumer NEVER called
```

---

### Flow 2: Client connects with INVALID token

```
Client                Nginx                    Middleware                         Consumer
   │                    │                          │                                  │
   ├── GET /ws/telemetry/?token=bad ─►│            │                                  │
   │    Upgrade: websocket            │            │                                  │
   │                    ├── Forward to web:8000 ──►│                                  │
   │                    │                          │                                  │
   │                    │                          ├── Parse query_string             │
   │                    │                          │   token = "bad"                  │
   │                    │                          │                                  │
   │                    │                          ├── await _get_user_from_token()   │
   │                    │                          │   └── DB lookup (in thread)      │
   │                    │                          │   └── WebSocketToken.DoesNotExist│
   │                    │                          │   └── return None                │
   │                    │                          │                                  │
   │                    │                          ├── Log: "websocket.auth_failed"   │
   │                    │                          │   reason: "invalid_token"        │
   │                    │                          │                                  │
   │◄─────────────────────── websocket.accept ─────┤                                  │
   │◄─────────────────────── websocket.close ──────┤  code: 4002                      │
   │                    │                          │                                  │
   ✗ Connection closed  │                          │              Consumer NEVER called
```

---

### Flow 3: Client connects with VALID token

```
Client                Nginx                    Middleware                         Consumer
   │                    │                          │                                  │
   ├── GET /ws/telemetry/?token=abc ─►│            │                                  │
   │    Upgrade: websocket            │            │                                  │
   │                    ├── Forward to web:8000 ──►│                                  │
   │                    │                          │                                  │
   │                    │                          ├── Parse query_string             │
   │                    │                          │   token = "abc..."               │
   │                    │                          │                                  │
   │                    │                          ├── await _get_user_from_token()   │
   │                    │                          │   └── DB lookup (in thread)      │
   │                    │                          │   └── Found! return user         │
   │                    │                          │                                  │
   │                    │                          ├── scope["user"] = user           │
   │                    │                          │                                  │
   │                    │                          ├── Log: "websocket.auth_success"  │
   │                    │                          │                                  │
   │                    │                          ├── await self.app(scope, ...) ───►│
   │                    │                          │                                  │
   │                    │                          │                   Consumer.connect()
   │◄──────────────────────────────────────────────────────── websocket.accept ───────┤
   │                    │                          │                                  │
   │                    │                          │              connected_clients.add(self)
   │                    │                          │                                  │
   │                    │                          │              if first client:    │
   │                    │                          │                start_telemetry_consumer()
   │                    │                          │                                  │
   │◄──────────────────────────────────────────────────────── Welcome JSON ───────────┤
   │  {                 │                          │                                  │
   │    "type": "connection",                      │                                  │
   │    "status": "connected",                     │                                  │
   │    "user": "testuser",                        │                                  │
   │    "subscriptions": [],                       │                                  │
   │    "message": "Connected..."                  │                                  │
   │  }                 │                          │                                  │
   │                    │                          │                                  │
   ✓ Connection established                        │                                  │
   │                    │                          │                                  │
   ├── {"action": "subscribe", "devices": ["DEV-1"]} ────────────────────────────────►│
   │                    │                          │                                  │
   │◄───────────────────────────────────── {"type": "subscription", ...} ─────────────┤
   │                    │                          │                                  │
   │         ... Kafka messages broadcasted to client ...                             │
```

---

### Summary

| Scenario | Middleware | Consumer | Close Code |
|----------|------------|----------|------------|
| No token | Rejects | Never called | 4001 |
| Invalid token | Rejects | Never called | 4002 |
| Valid token | Passes through | `connect()` runs | - (stays open) |

## API Reference

### Get Authentication Token

**Endpoint:** `GET /api/v1/auth/fake` or `POST /api/v1/auth/fake`

**Description:** Returns a WebSocket authentication token for testing purposes.

**Request (POST with custom username):**
```json
{
  "username": "custom_user"
}
```

**Response:**
```json
{
  "token": "f0c8c7fec7bd3b5203ae3f4468ad130d0d28dc91dd432c2b5764186512629465",
  "username": "testuser"
}
```

### WebSocket Connection

**Endpoint:** `wss://host/ws/telemetry/?token=<token>`

**Query Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| token | Yes | 64-character hex token from auth endpoint |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| 4001 | No Token | Connection attempted without token in query string |
| 4002 | Invalid Token | Token not found in database or expired |

## Example Usage

```bash
# 1. Get a token
TOKEN=$(curl -sk https://localhost/api/v1/auth/fake | jq -r '.token')

# 2. Connect with token
wscat -n -c "wss://localhost/ws/telemetry/?token=$TOKEN"
```

## Demo Dashboard

A visual demo dashboard is available at:

```
https://localhost/demo/
```

Features:
- One-click authentication
- Subscribe/unsubscribe to devices
- Real-time telemetry display
- Message log

## Implementation Details

### Files

| File | Description |
|------|-------------|
| `apps/core/models.py` | `WebSocketToken` model |
| `apps/telemetry/middleware.py` | `WebSocketTokenAuthMiddleware` |
| `apps/core/views.py` | `fake_auth` endpoint |
| `config/asgi.py` | Middleware configuration |
| `frontend/demo.html` | Demo dashboard |

### WebSocketToken Model

```python
class WebSocketToken(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create_for_user(cls, user) -> 'WebSocketToken':
        return cls.objects.create(user=user, token=secrets.token_hex(32))
```

### Middleware Flow

1. Extract token from query string
2. Look up token in database (async via `database_sync_to_async`)
3. If valid: set `scope["user"]` and pass to consumer
4. If invalid: accept connection, then close with error code

## Security Considerations

- Tokens are 64-character random hex strings (256 bits of entropy)
- Tokens are stored in database, linked to Django User
- The `/api/v1/auth/fake` endpoint is for **development only**
- In production, integrate with your real authentication system (OAuth, JWT, etc.)

## Testing

Run authentication tests:

```bash
docker compose exec web pytest apps/telemetry/tests/test_ws_auth.py -v
```
