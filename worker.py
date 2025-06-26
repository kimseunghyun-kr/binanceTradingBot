import logging
import os

from app.core.celery_app import celery

# Import tasks to ensure they are registered with Celery

# Configure logging for the worker (separate log file)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/worker.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    # Start Celery worker (this will block and run indefinitely)
    celery.worker_main(argv=["worker", "--loglevel=info"])
