from django.http import HttpResponse
from prometheus_client import generate_latest


def index(request):
    return HttpResponse("IoT Hub Alpha: System Online")


def health(request):
    return HttpResponse("ok")


def metrics(request):
    """Expose Prometheus metrics endpoint."""
    return HttpResponse(
        generate_latest(),
        content_type="text/plain; charset=utf-8",
    )
