import contextvars
import logging
from typing import Optional


class _LoggingContext:
    def __init__(self) -> None:
        self.request_method: contextvars.ContextVar[Optional[str]] = (
            contextvars.ContextVar("request_method", default=None)
        )
        self.request_path: contextvars.ContextVar[Optional[str]] = (
            contextvars.ContextVar("request_path", default=None)
        )
        self.request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
            "request_id", default=None
        )
        self.task_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
            "task_id",
            default=None,
        )
        self.task_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
            "task_name",
            default=None,
        )


_context = _LoggingContext()


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        if not super().filter(record):
            return False
        record.request_id = _context.request_id.get()
        record.request_method = _context.request_method.get()
        record.request_path = _context.request_path.get()
        record.task_id = _context.task_id.get()
        record.task_name = _context.task_name.get()
        return True


def bind_request_context(request):
    request_id = getattr(request, "request_id", None)
    if not request_id and hasattr(request, "headers"):
        request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = request.META.get("HTTP_X_REQUEST_ID")
    _context.request_id.set(request_id)
    _context.request_method.set(getattr(request, "method", None))
    _context.request_path.set(getattr(request, "path", None))


def clear_request_context():
    _context.request_id.set(None)
    _context.request_method.set(None)
    _context.request_path.set(None)


def setup_celery_logging_context():
    try:
        from celery.signals import task_postrun, task_prerun
    except ImportError as exc:
        logging.getLogger(__name__).exception(
            "logging.celery_signals_import_failed",
            extra={"error": str(exc)},
        )
        return

    @task_prerun.connect(weak=False)
    def _task_prerun(task_id=None, task=None, **_kwargs):
        _context.task_id.set(task_id)
        _context.task_name.set(getattr(task, "name", None))

    @task_postrun.connect(weak=False)
    def _task_postrun(**_kwargs):
        _context.task_id.set(None)
        _context.task_name.set(None)
