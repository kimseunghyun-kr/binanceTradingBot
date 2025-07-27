# app/celery_app.py
"""Celery bootstrap that shares the same configuration pools and initializes on worker start."""
import importlib
# import sys
# print("Celery sys.path:", sys.path)
#
import os
import sys

import anyio
from celery import Celery
from celery.signals import worker_process_init, worker_shutdown, worker_init

from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import open_pools, close_pools
from app.core.pydanticConfig.settings import get_settings
from app.services.orchestrator import Docker_Engine
from app.services.orchestrator.OrchestratorService import OrchestratorService

# Load settings and initialize MongoDBConfig pools (no DB connections opened yet)

print("▶️  CELERY STARTUP")
print("   CWD =", os.getcwd())
print("   sys.path[0] =", sys.path[0])
print("   full sys.path =", sys.path, "\n")



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
celery.autodiscover_tasks(["app"])

@worker_init.connect
def on_worker_init(**kwargs):
    # Runs once in the worker master process.
    logging.info("Celery worker_init: ensuring orchestrator image…")
    Docker_Engine.initialize()  # idempotent
    try:
        Docker_Engine.ensure_orchestrator_image(
            force_rebuild=getattr(cfg, "ORCH_REBUILD_ON_START", False)
        )
        logging.info("Orchestrator image ready.")
    except Exception:
        logging.exception("Failed to ensure orchestrator image at worker_init.")
        # Optionally re-raise to fail fast:
        # raise

# ─── Open pools in each worker process ─────────────────────────────────
@worker_process_init.connect
def on_worker_process_init(**kwargs):
    # Connect Postgres, Redis, and MongoDB in this worker process
    anyio.run(open_pools)
    print("▶️  WORKER_PROCESS_INIT")
    print("    CWD         =", os.getcwd())
    print("    sys.path[0] =", sys.path[0])
    print("    full sys.path =", sys.path)
    spec = importlib.util.find_spec("entities")
    print("    entities spec  =", spec)

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
