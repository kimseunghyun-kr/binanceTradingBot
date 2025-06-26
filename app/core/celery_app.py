from celery import Celery

from app.pydanticConfig.settings import settings

# Create Celery app with Redis broker and backend
celery = Celery("binanceTradingBot")
celery.conf.broker_url = settings.REDIS_BROKER_URL
celery.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Celery configuration (if needed, e.g., serializers)
celery.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])

# Auto-discover tasks modules (ensure tasks package is imported)
celery.autodiscover_tasks(["app.tasks"])
