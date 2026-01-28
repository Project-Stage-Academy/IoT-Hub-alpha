from celery import shared_task

@shared_task(bind=True)
def process_telemetry(self):
    print("Processing.....")