import importlib
import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

from .logging import bind_request_context, clear_request_context
from .metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = logging.getLogger("request.lifecycle")


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _get_request_id(self, request):
        request_id = getattr(request, "request_id", None)
        if request_id:
            return request_id

        generator_path = getattr(
            settings,
            "REQUEST_ID_GENERATOR",
            "request_id.uuid4",
        )
        try:
            module_name, func_name = generator_path.rsplit(".", 1)
            generator = getattr(importlib.import_module(module_name), func_name)
            return generator()
        except (ImportError, AttributeError) as exc:
            logging.getLogger(__name__).warning(
                "request_id_generator_load_failed",
                extra={"error": str(exc)},
            )
            return str(uuid.uuid4())

    def __call__(self, request):
        request.request_id = self._get_request_id(request)
        bind_request_context(request)

        # Record request start time for metrics
        start_time = time.perf_counter()
        status_code = 500  # Default for errors

        try:
            response = self.get_response(request)
            status_code = response.status_code
            request_id = getattr(request, "request_id", None)
            if request_id:
                header = getattr(settings, "REQUEST_ID_RESPONSE_HEADER", "X-Request-ID")
                response[header] = request_id
            return response
        finally:
            # Record request latency and count even if an error occurred
            latency = time.perf_counter() - start_time
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.path,
            ).observe(latency)

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.path,
                status=str(status_code),
            ).inc()
            clear_request_context()


class RateLimitingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "RATE_LIMIT_ENABLED", False):
            return self.get_response(request)

        ip_address = self.get_client_ip(request)
        if not ip_address:
            logger.warning(
                "rate_limit_ip_missing",
                extra={"path": request.path},
            )
            return JsonResponse(
                {"error": "Unable to determine client IP."},
                status=400,
            )

        if request.path.startswith("/admin"):
            limit_count = getattr(settings, "RATE_LIMIT_ADMIN_COUNT", 60)
            limit_period = getattr(settings, "RATE_LIMIT_ADMIN_PERIOD", 60)
        elif "telemetry" in request.path:
            limit_count = getattr(settings, "RATE_LIMIT_DEVICE_COUNT", 100)
            limit_period = getattr(settings, "RATE_LIMIT_DEVICE_PERIOD", 60)
        else:
            limit_count = getattr(settings, "RATE_LIMIT_DEFAULT_COUNT", 60)
            limit_period = getattr(settings, "RATE_LIMIT_DEFAULT_PERIOD", 60)

        cache_key = f"rate_limit_{ip_address}_{request.path}"

        current_count = cache.get(cache_key)
        if current_count is None:
            cache.set(cache_key, 1, timeout=limit_period)
        else:
            if current_count >= limit_count:
                return JsonResponse({"error": "Too many requests."}, status=429)
            cache.incr(cache_key)

        return self.get_response(request)
