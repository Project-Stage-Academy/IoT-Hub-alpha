import os
import time

from celery import Celery, signals

settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Celery task metrics tracking
@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Record task start time for duration calculation."""
    from config.metrics import CELERY_TASKS_TOTAL

    # Store start time on task for duration calculation in postrun
    task._start_time = time.time()


@signals.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, state=None, **kwargs):
    """Record task completion metrics."""
    from config.metrics import CELERY_TASKS_TOTAL, CELERY_TASK_DURATION_SECONDS

    # Record task as completed
    CELERY_TASKS_TOTAL.labels(
        task_name=task.name,
        status="success",
    ).inc()

    # Record task duration if start time was recorded
    if hasattr(task, "_start_time"):
        duration = time.time() - task._start_time
        CELERY_TASK_DURATION_SECONDS.labels(
            task_name=task.name,
        ).observe(duration)
        del task._start_time


@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Record task failure metrics."""
    from config.metrics import CELERY_TASKS_TOTAL

    CELERY_TASKS_TOTAL.labels(
        task_name=sender.name,
        status="failure",
    ).inc()
