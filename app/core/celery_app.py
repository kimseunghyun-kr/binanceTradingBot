from celery import Celery
from app.pydanticConfig.settings import settings

celery = Celery("binanceTradingBot")
celery.conf.broker_url = settings.REDIS_BROKER_URL
celery.conf.result_backend = settings.CELERY_RESULT_BACKEND
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# THIS is all you need for autodiscover:
celery.autodiscover_tasks(['app.tasks'])
print("imported celery with tasks")
print(list(celery.tasks.keys()))


# For debug:
import logging
logging.info(f"Registered tasks: {list(celery.tasks.keys())}")
