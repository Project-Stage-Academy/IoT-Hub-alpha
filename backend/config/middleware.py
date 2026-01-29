import importlib
import logging
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

from .logging import bind_request_context, clear_request_context

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
            "request_id.generators.uuid4",
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
        context_bound = False
        try:
            bind_request_context(request)
            context_bound = True
            response = self.get_response(request)
            request_id = getattr(request, "request_id", None)
            if request_id:
                header = getattr(settings, "REQUEST_ID_RESPONSE_HEADER", "X-Request-ID")
                response[header] = request_id

            return response
        finally:
            if context_bound:
                clear_request_context()


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
        request_history = cache.get(cache_key, [])

        current_time = time.time()
        valid_requests = [t for t in request_history if t > current_time - limit_period]

        if len(valid_requests) >= limit_count:
            return JsonResponse({"error": "Too many requests."}, status=429)

        valid_requests.append(current_time)
        cache.set(cache_key, valid_requests, limit_period)

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
