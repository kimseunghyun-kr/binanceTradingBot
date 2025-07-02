import logging
import os

from config_profile import PROFILE

dotenv_file = f".env.{PROFILE}" if os.path.exists(f".env.{PROFILE}") else ".env"
from dotenv import load_dotenv

load_dotenv(dotenv_file)

from app.core.celery_app import celery

# Configure logging for the worker (to both file and console if desired)
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/worker.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

logging.info("hello this is worker")
logging.info(f"Registered tasks: {list(celery.tasks.keys())}")

if __name__ == "__main__":
    celery.worker_main(argv=["worker", "--loglevel=info"])
