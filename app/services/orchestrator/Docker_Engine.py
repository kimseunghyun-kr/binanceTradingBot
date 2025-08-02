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
    return os.getenv("DOCKER_NETWORK") or getattr(_settings, "DOCKER_NETWORK", None)

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
        _client.ping()  # raises if DinD not healthy
        info = _client.version()
        logging.info("docker_engine: connected to Docker %s (API %s)", info["Version"], info["ApiVersion"])
        logging.info("docker_engine: Docker client initialized.")
    except DockerException as e:
        logging.error(f"docker_engine: failed to initialize Docker client: {e}")
        raise

def locate_project_root_with_dockerfile(start: Path,
                                        target_subpath: str = "strategyOrchestrator/Dockerfile",
                                        max_up_levels: int = 5,
                                        max_down_search_depth: int = 3) -> Path:
    """
    Try to find the project root containing strategyOrchestrator/Dockerfile.
    1. Walk upward up to max_up_levels looking for <dir>/strategyOrchestrator/Dockerfile.
    2. If not found, do a limited depth downward search from start.
    Returns the project root (the directory that contains strategyOrchestrator).
    """
    start = start.resolve()

    # 1. Upward walk
    current = start
    for _ in range(max_up_levels):
        candidate = current / "strategyOrchestrator" / "Dockerfile"
        if candidate.is_file():
            return current  # project root
        if current.parent == current:
            break
        current = current.parent

    # 2. Bounded downward search (breadth-first up to depth)
    def walk_limited(root: Path, depth: int):
        if depth < 0:
            return None
        # check if strategyOrchestrator exists here
        so_dir = root / "strategyOrchestrator"
        dockerfile = so_dir / "Dockerfile"
        if dockerfile.is_file():
            return root
        for child in root.iterdir():
            if child.is_dir():
                found = walk_limited(child, depth - 1)
                if found:
                    return found
        return None

    found_root = walk_limited(start, max_down_search_depth)
    if found_root:
        return found_root

    raise FileNotFoundError(f"Could not locate '{target_subpath}' from {start} (up {max_up_levels}, down {max_down_search_depth})")

def resolve_service_ip(network_name: str, container_name: str) -> str | None:
    """
    Returns the IPv4 address (no CIDR) of container_name on network_name, looking
    at the outer Docker daemon via the unix socket.
    """
    try:
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        network = client.networks.get(network_name)
        containers = network.attrs.get("Containers", {}) or {}
        for info in containers.values():
            if info.get("Name") == container_name:
                ipv4 = info.get("IPv4Address", "")
                if ipv4:
                    return ipv4.split("/")[0]
        logging.warning("Container %s not found on network %s", container_name, network_name)
    except Exception as e:
        logging.error("Failed to resolve %s on %s: %s", container_name, network_name, e)
    return None


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
    if not dockerfile_path.exists() and not dockerfile_path.is_file():
        dockerfile_path = locate_project_root_with_dockerfile(project_root)
    # fallback
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

    logger.info("built image id: %s", img.id)

    for log in logs:
        stream = log.get("stream")
        if stream:
            logging.debug(stream.strip())

    logging.info(f"docker_engine: built image {_image_name}")
    _image_built = True
    return img
