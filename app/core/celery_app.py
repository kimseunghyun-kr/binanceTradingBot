# app/core/celery_app.py
from celery import Celery

from app.core.pydanticConfig.settings import get_settings

settings = get_settings()

def create_celery() -> Celery:
    app = Celery("binanceTradingBot",
                 broker=settings.REDIS_BROKER_URL,
                 backend=settings.CELERY_RESULT_BACKEND)

    app.conf.update(
        broker_url=settings.REDIS_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )

    app.autodiscover_tasks(["app.tasks"])
    return app


celery = create_celery()

# For debug
import logging, pprint
logging.info("Celery tasks loaded:\n%s", pprint.pformat(list(celery.tasks)))
