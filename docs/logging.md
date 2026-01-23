# Logging and Observability


## How logging works 
1. `request_id` middleware assigns or reads `X-Request-ID` and stores it on `request.request_id`.
2. `RequestContextMiddleware` stores `request_id`, `request_method`, and `request_path` in context variables.
3. `RequestContextMiddleware` adds `X-Request-ID` to the HTTP response.
4. Celery signals set `task_id` and `task_name` during task execution.
5. The logging filters inject `request_id`, `request_method`, `request_path`, `task_id`, and `task_name` into every log record.
6. The JSON formatter renders each log record as one JSON line with `timestamp`, `level`, and `logger`.
7. Docker `json-file` log driver rotates files locally.

## Step-by-step logging flow
1. `RequestIdMiddleware` assigns or reads the request id into `request.request_id`.
2. `RequestContextMiddleware` reads or generates a request id and binds it to the logging context.
3. Your code logs using a logger (module logger or event logger).
4. Logging filters attach request and task context to the record.
5. The JSON formatter outputs one JSON line per record.
6. Docker handles rotation for local logs.

## Logger naming conventions
| Intent | Example logger | When to use |
| --- | --- | --- |
| Event-focused | `logging.getLogger("request.lifecycle")` | Consistent, filterable event categories. |
| Module-focused | `logging.getLogger(__name__)` | Show the exact module where the log originates. |

## Required dependencies
- `python-json-logger`
- `django-request-id`

These are already listed in `backend/requirements.txt`.

## Django configuration overview
Key settings live in `backend/config/settings/base.py`:
- `request_id.middleware.RequestIdMiddleware`
- `config.middleware.RequestContextMiddleware`
- `LOGGING_BASE` with JSON formatter and filters
- `REQUEST_ID_*` settings

## Example JSON log
```json
{"message":"request.completed","request_id":"test-123","request_method":"POST","request_path":"/test","task_id":null,"task_name":null,"timestamp":"2026-01-22 09:55:30,326","level":"INFO","logger":"request.lifecycle"}
```

## How to read logs locally
```bash
docker compose logs -f web
docker compose logs -f worker
```

To view a single container:
```bash
docker logs -f iot_hub_web
```

To confirm request id is present:
```bash
curl -i http://localhost:8000/ | rg -i "x-request-id"
```

## How to add logs in code
### Django/DRF view
```python
import logging

logger = logging.getLogger(__name__)

def list_devices(request):
    logger.info("Listing devices")
```

### Celery task
```python
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task
def sync_devices():
    logger.info("Sync started")
```

### Add structured fields
```python
logger.info(
    "Device updated",
    extra={"device_id": device.id, "status": device.status},
)
```

### Log exceptions
```python
try:
    ...
except Exception:
    logger.exception("Device update failed")
```

## Log rotation (local Docker)
Docker is configured with the `json-file` driver and rotation:
- `max-size`: 10 MB
- `max-file`: 3

## Parsing in log aggregators
Each log line is JSON. Recommended field mapping:
- `timestamp` -> `@timestamp`
- `level` -> `log.level`
- `logger` -> `log.logger`
- `request_id` -> `trace.id` or `request.id`
- `task_id` -> `celery.task_id`
- `task_name` -> `celery.task_name`

If a pre-filter regex is needed before JSON parsing:
```
"^\{.*\}$"
```
