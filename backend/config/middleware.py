import importlib
import logging
import uuid

from django.conf import settings

from .logging import bind_request_context


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
        response = self.get_response(request)
        request_id = getattr(request, "request_id", None)
        if request_id:
            header = getattr(settings, "REQUEST_ID_RESPONSE_HEADER", "X-Request-ID")
            response[header] = request_id

        return response
