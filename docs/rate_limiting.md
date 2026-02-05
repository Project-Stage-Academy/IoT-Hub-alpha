# Rate Limiting

This project includes a simple rate-limiting middleware to protect against brute-force attacks and prevent system abuse. This document explains how it works and how to configure it.

## How It Works

The `RateLimitingMiddleware` is a custom Django middleware located in `backend/config/middleware.py`. It uses Django's caching backend to track the number of requests from each IP address over a specific period.

If the number of requests from an IP exceeds the configured limit, the middleware will return a `429 Too Many Requests` error.

Important: Each endpoint can have separate limits if the cache key includes the path. By default, the middleware uses the IP address only, so all endpoints share the same limit. For stricter separation, the cache key can be updated to:

```python
cache_key = f"rate_limit_{ip_address}_{request.path}"
```

## Adding Middleware

Ensure the middleware is included in your Django MIDDLEWARE list (`backend/config/settings/base.py`):
```python
MIDDLEWARE = [
    ...
    "config.middleware.RateLimitingMiddleware",
    ...
]
```

## Configuration

The rate limiter can be configured in your Django settings file (`backend/config/settings/base.py` or an environment-specific file like `local.py`). The settings can also be controlled via environment variables.

### Enabling/Disabling

-   **`RATE_LIMIT_ENABLED`**: Set to `True` to enable the middleware.
    -   Environment Variable: `RATE_LIMIT_ENABLED` (`True`/`False`)
    -   Recommended: For local dev, you can set `False` to avoid blocking rapid testing.

### Rate Limits

The middleware defines three different buckets for rate limits:

1.  **Default**: Applies to most API endpoints.
    -   `RATE_LIMIT_DEFAULT_COUNT`: Number of requests allowed. (Default: 60)
    -   `RATE_LIMIT_DEFAULT_PERIOD`: The time period in seconds. (Default: 60)

2.  **Admin**: A stricter limit for the Django admin interface (`/admin/`).
    -   `RATE_LIMIT_ADMIN_COUNT`: (Default: 20)
    -   `RATE_LIMIT_ADMIN_PERIOD`: (Default: 60)

3.  **Device Ingestion**: A more generous limit for device telemetry endpoints (paths containing `telemetry`).
    -   `RATE_LIMIT_DEVICE_COUNT`: (Default: 100)
    -   `RATE_LIMIT_DEVICE_PERIOD`: (Default: 60)

### Example Configuration (`.env` file)

To enable rate limiting and override the default limits, you can add the following to your `.env` file:

```dotenv
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT_COUNT=100
RATE_LIMIT_DEFAULT_PERIOD=60
RATE_LIMIT_ADMIN_COUNT=15
RATE_LIMIT_DEVICE_COUNT=200
```

## Recommended Defaults

The default values set in `settings/base.py` are sensible for a typical production environment, but they can be tuned based on traffic patterns.

-   **Device Ingestion Endpoints** (`/api/v1/telemetry/`):
    -   **Recommendation**: 100-200 requests per minute.
    -   **Reasoning**: Devices may need to send data frequently. This limit should be high enough to accommodate normal device behavior but low enough to prevent a single misbehaving device from overwhelming the system.

-   **Admin Endpoints** (`/admin/`):
    -   **Recommendation**: 15-30 requests per minute.
    -   **Reasoning**: This helps protect the admin login page from brute-force password guessing attacks. Legitimate admin usage is typically low-frequency.

-   **General API Endpoints**:
    -   **Recommendation**: 60 requests per minute.
    -   **Reasoning**: A standard and reasonable limit for most APIs, preventing aggressive scraping or minor abuse while allowing normal user interaction.

## Runtime Behavior & Notes

- Cache keys track request history per IP (and optionally per path).

- Changing environment variables and reloading Django allows dynamic adjustment of limits.

- In dev/staging, consider disabling rate limiting (`RATE_LIMIT_ENABLED=False`) to speed up testing.

## Middleware Code Reference

For reference, the implementation can be found in `backend/config/middleware.py`:

```python
import time
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

class RateLimitingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "RATE_LIMIT_ENABLED", False):
            return self.get_response(request)

        ip_address = self.get_client_ip(request)
        if not ip_address:
            return self.get_response(request)

        # Define limits based on path
        if request.path.startswith('/admin'):
            limit_count = getattr(settings, "RATE_LIMIT_ADMIN_COUNT", 20)
            limit_period = getattr(settings, "RATE_LIMIT_ADMIN_PERIOD", 60)
        elif 'telemetry' in request.path:
            limit_count = getattr(settings, "RATE_LIMIT_DEVICE_COUNT", 100)
            limit_period = getattr(settings, "RATE_LIMIT_DEVICE_PERIOD", 60)
        else:
            limit_count = getattr(settings, "RATE_LIMIT_DEFAULT_COUNT", 60)
            limit_period = getattr(settings, "RATE_LIMIT_DEFAULT_PERIOD", 60)

        cache_key = f"rate_limit_{ip_address}_{request.path}"  # Optional: track separately per endpoint
        request_history = cache.get(cache_key, [])

        current_time = time.time()
        valid_requests = [t for t in request_history if t > current_time - limit_period]

        if len(valid_requests) >= limit_count:
            return JsonResponse({"error": "Too many requests."}, status=429)

        valid_requests.append(current_time)
        cache.set(cache_key, valid_requests, limit_period)

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```
