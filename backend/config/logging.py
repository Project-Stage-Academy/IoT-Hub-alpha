import contextvars
import logging
from typing import Optional

_request_method: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_method",
    default=None,
)
_request_path: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_path",
    default=None,
)
_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_task_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "task_id",
    default=None,
)
_task_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "task_name",
    default=None,
)


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = _request_id.get()
        record.request_method = _request_method.get()
        record.request_path = _request_path.get()
        record.task_id = _task_id.get()
        record.task_name = _task_name.get()
        return True


def bind_request_context(request):
    request_id = getattr(request, "request_id", None)
    if not request_id and hasattr(request, "headers"):
        request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = request.META.get("HTTP_X_REQUEST_ID")
    _request_id.set(request_id)
    _request_method.set(getattr(request, "method", None))
    _request_path.set(getattr(request, "path", None))


def clear_request_context():
    _request_id.set(None)
    _request_method.set(None)
    _request_path.set(None)


def setup_celery_logging_context():
    try:
        from celery.signals import task_postrun, task_prerun
    except Exception:
        return

    @task_prerun.connect(weak=False)
    def _task_prerun(task_id=None, task=None, **_kwargs):
        _task_id.set(task_id)
        _task_name.set(getattr(task, "name", None))

    @task_postrun.connect(weak=False)
    def _task_postrun(**_kwargs):
        _task_id.set(None)
        _task_name.set(None)
