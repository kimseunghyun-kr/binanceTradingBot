# app/celery_app.py
"""Celery bootstrap that shares the same configuration pools and initializes on worker start."""

from celery import Celery
from celery.signals import worker_process_init, worker_shutdown
import anyio

from app.core.pydanticConfig.settings import get_settings
from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import open_pools, close_pools

# Load settings and initialize MongoDBConfig pools (no DB connections opened yet)
cfg = get_settings()
MongoDBConfig.initialize()

# Create Celery app
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

# ─── Open pools in each worker process ─────────────────────────────────
@worker_process_init.connect
def on_worker_process_init(**kwargs):
    # Connect Postgres, Redis, and MongoDB in this worker process
    anyio.run(open_pools)

# ─── Close pools when worker shuts down ────────────────────────────────
@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    # Gracefully close all pools
    close_pools()

# Optional: log loaded tasks for debug
if __name__ == "__main__":
    import logging, pprint
    logging.basicConfig(level=logging.INFO)
    logging.info("Celery tasks loaded:\n%s", pprint.pformat(list(celery.tasks)))
