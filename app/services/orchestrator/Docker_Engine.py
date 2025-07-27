"""
docker_engine.py
────────────────────────────────────────────────────────────
A tiny, dependency-light singleton around docker.from_env().
Safe to import from init_services.py and OrchestratorService.py.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import docker
from celery.utils.log import get_task_logger
from docker.client import DockerClient
from docker.errors import DockerException, ImageNotFound
from docker.models.images import Image

from app.core.pydanticConfig.settings import get_settings

_settings = get_settings()

_client: Optional[DockerClient] = None
_image_built: bool = False
_image_name: str = "tradingbot_orchestrator:latest"
logger = get_task_logger(__name__)

def client() -> DockerClient:
    """Return the initialized Docker client; raise if not initialized."""
    if _client is None:
        raise RuntimeError("docker_engine not initialized. Call docker_engine.initialize() early.")
    return _client


def image_name() -> str:
    return _image_name

def _compose_network_name() -> Optional[str]:
    return getattr(_settings, "DOCKER_NETWORK", None)

def _to_service_uri(uri: str | None, service: str, port: int, default_db: str | None = None) -> str:
    base = f"mongodb://{service}:{port}"
    if not uri or uri.strip() == "":
        return f"{base}/{default_db}" if default_db else base
    return uri.replace("localhost", service).replace("127.0.0.1", service)


def initialize() -> None:
    """
    Lightweight init: create client and, optionally, ensure image.
    Idempotent and safe to call many times.
    """
    global _client
    if _client is not None:
        return
    try:
        _client = docker.from_env()
        logging.info("docker_engine: Docker client initialized.")
    except DockerException as e:
        logging.error(f"docker_engine: failed to initialize Docker client: {e}")
        raise


def ensure_orchestrator_image(force_rebuild: bool = False) -> Image:
    """
    Ensure the orchestrator image exists. Idempotent.
    Separated so init_services can eagerly build once at boot.
    """
    global _image_built
    if _image_built and not force_rebuild:
        # already ensured in this process
        return client().images.get(_image_name)

    try:
        if not force_rebuild:
            img = client().images.get(_image_name)
            logging.info(f"docker_engine: image {_image_name} already present.")
            _image_built = True
            return img
    except ImageNotFound:
        pass

    project_root = Path(_settings.BASE_DIR)
    dockerfile_path =  project_root / "strategyOrchestrator" / "Dockerfile"
    if not dockerfile_path.exists():
        raise FileNotFoundError(f"docker_engine: build path not found: {dockerfile_path}")

    logging.info(f"docker_engine: building image {_image_name} from {dockerfile_path}")
    img, logs = client().images.build(
        path=os.fspath(project_root),
        dockerfile=os.fspath(dockerfile_path.relative_to(project_root)),
        tag=_image_name,
        rm=True,
        forcerm=True,
        pull=False,
        nocache=force_rebuild,
    )

    logger.error("built image id: %s", img.id)

    for log in logs:
        stream = log.get("stream")
        if stream:
            logging.debug(stream.strip())

    logging.info(f"docker_engine: built image {_image_name}")
    _image_built = True
    return img
