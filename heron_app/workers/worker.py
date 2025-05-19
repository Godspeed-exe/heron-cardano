from celery import Celery
import os


celery = Celery(
    "heron_app",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    )

# Accept any queue by default
celery.conf.task_queues = []
celery.conf.task_routes = {}

from heron_app.workers import tasks 