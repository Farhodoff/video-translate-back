from celery import Celery
import os

# Get Redis connection string from environment or use default localhost
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "backend",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks"]
)

# Optional configuration, see the Celery application user guide.
celery_app.conf.update(
    result_expires=3600,
    task_track_started=True,
    broker_connection_retry_on_startup=True
)

if __name__ == '__main__':
    celery_app.start()
