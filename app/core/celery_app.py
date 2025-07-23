# app/core/celery_app.py
from celery import Celery

from app.core.pydanticConfig import settings


def create_celery() -> Celery:
    app = Celery("binanceTradingBot",
                 broker=settings.REDIS_BROKER_URL,
                 backend=settings.CELERY_RESULT_BACKEND)

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    )

    app.autodiscover_tasks(["app.tasks"])
    return app


celery = create_celery()

# For debug
import logging, pprint
logging.info("Celery tasks loaded:\n%s", pprint.pformat(list(celery.tasks)))
