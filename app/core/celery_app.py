"""Celery bootstrap that shares the same configuration pools."""

from celery import Celery
from app.core.pydanticConfig.settings import get_settings
from app.core.db.mongodb_config import MongoDBConfig

cfg = get_settings()
MongoDBConfig.initialize()           # shared pools for every worker

celery: Celery = Celery(
    "kwontbot",
    broker=cfg.REDIS_BROKER_URL,
    backend=cfg.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

celery.autodiscover_tasks(["app.tasks"])

# ─── optional: log loaded tasks for debug ──────────────────────────────
if __name__ == "__main__":
    import logging, pprint
    logging.basicConfig(level=logging.INFO)
    logging.info("Celery tasks loaded:\n%s", pprint.pformat(list(celery.tasks)))
