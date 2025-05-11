from celery import Celery
import os

broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

celery = Celery(
    "heron_worker",
    broker=broker_url,
    backend=broker_url,
    include=["heron_app.workers.tasks"]
)

celery.conf.task_routes = {
    "heron_app.workers.tasks.process_transaction": {"queue": "transactions"},
}