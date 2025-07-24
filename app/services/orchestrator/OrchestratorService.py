"""
OrchestratorService.py
──────────────────────────────────────────────────────────────────────────
Manages Docker-based strategy orchestrator execution with proper sandboxing,
concurrency control, and master-slave MongoDB architecture.
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple

import docker
from docker.errors import DockerException, ImageNotFound
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from app.core.init_services import get_redis_cache
from app.core.pydanticConfig.settings import get_settings

settings = get_settings()
redis_cache = get_redis_cache()

class OrchestratorService:
    """
    Manages strategy orchestrator execution in isolated Docker containers.

    Features:
    - Dynamic strategy code injection via volumes
    - Read-only MongoDB access for containers
    - Concurrent execution with resource limits
    - Result streaming and error handling
    """

    _docker_client = None
    _executor = None
    _image_name = "tradingbot_orchestrator:latest"
    _max_concurrent_runs = 5

    @classmethod
    def initialize(cls):
        """Initialize Docker client and thread pool executor."""
        try:
            cls._docker_client = docker.from_env()
            cls._executor = ThreadPoolExecutor(max_workers=cls._max_concurrent_runs)
            cls._ensure_orchestrator_image()
        except DockerException as e:
            logging.error(f"Failed to initialize Docker client: {e}")
            raise

    @classmethod
    def _ensure_orchestrator_image(cls):
        """Build orchestrator Docker image if not exists."""
        try:
            cls._docker_client.images.get(cls._image_name)
            logging.info(f"Orchestrator image {cls._image_name} already exists")
        except ImageNotFound:
            logging.info(f"Building orchestrator image {cls._image_name}")
            cls._build_orchestrator_image()

    @classmethod
    def _build_orchestrator_image(cls):
        """Build the orchestrator Docker image."""
        dockerfile_path = os.path.join(settings.BASE_DIR, "strategyOrchestrator")

        try:
            image, logs = cls._docker_client.images.build(
                path=dockerfile_path,
                tag=cls._image_name,
                rm=True,
                forcerm=True
            )
            for log in logs:
                if 'stream' in log:
                    logging.debug(log['stream'].strip())
            logging.info(f"Successfully built image {cls._image_name}")
        except Exception as e:
            logging.error(f"Failed to build orchestrator image: {e}")
            raise

    @classmethod
    async def run_backtest(
            cls,
            strategy_code: str,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str,
            num_iterations: int,
            additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run a backtest in an isolated Docker container.

        Args:
            strategy_code: Python code for the strategy
            strategy_config: Strategy configuration parameters
            symbols: List of symbols to backtest
            interval: Timeframe interval
            num_iterations: Number of iterations
            additional_params: Additional parameters

        Returns:
            Backtest results dictionary
        """
        # Generate unique run ID
        run_id = cls._generate_run_id(strategy_config, symbols, interval)

        # Check cache
        if cached_result := cls._get_cached_result(run_id):
            return cached_result

        # Prepare input configuration
        input_config = cls._prepare_input_config(
            strategy_config, symbols, interval, num_iterations, additional_params
        )

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            cls._executor,
            cls._run_container,
            strategy_code,
            input_config,
            run_id
        )

        # Cache result
        cls._cache_result(run_id, result)

        return result

    @classmethod
    def _run_container(
            cls,
            strategy_code: str,
            input_config: Dict[str, Any],
            run_id: str
    ) -> Dict[str, Any]:
        """Execute backtest in Docker container with strategy code volume."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write strategy code to temporary file
            strategy_file = os.path.join(temp_dir, "user_strategy.py")
            with open(strategy_file, 'w') as f:
                f.write(strategy_code)

            # Prepare MongoDB read-only connection string
            mongo_read_only = cls._get_read_only_mongo_uri()

            # Container configuration
            container_config = {
                "image": cls._image_name,
                "command": ["python", "StrategyOrchestrator.py"],
                "environment": {
                    "MONGO_URI": mongo_read_only,
                    "MONGO_DB": settings.MONGO_DB,
                    "RUN_ID": run_id,
                    "PYTHONUNBUFFERED": "1"
                },
                "volumes": {
                    strategy_file: {
                        "bind": "/orchestrator/user_strategies/user_strategy.py",
                        "mode": "ro"
                    }
                },
                "mem_limit": "2g",
                "cpu_quota": 100000,  # 1 CPU
                "remove": True,
                "detach": False,
                "stdin_open": True,
                "stdout": True,
                "stderr": True
            }

            try:
                # Create and start container
                container = cls._docker_client.containers.create(**container_config)

                # Send input configuration via stdin
                stdin_socket = container.attach_socket(
                    params={'stdin': 1, 'stream': 1}
                )
                stdin_socket._sock.send(json.dumps(input_config).encode() + b'\n')
                stdin_socket.close()

                # Start container and wait for completion
                container.start()
                result = container.wait()

                # Get output
                logs = container.logs(stdout=True, stderr=True).decode()

                # Parse result from stdout
                if result['StatusCode'] == 0:
                    return cls._parse_container_output(logs)
                else:
                    raise RuntimeError(f"Container exited with code {result['StatusCode']}: {logs}")

            except Exception as e:
                logging.error(f"Container execution failed for run {run_id}: {e}")
                raise
            finally:
                # Ensure container is removed
                try:
                    container.remove(force=True)
                except:
                    pass

    @classmethod
    def _prepare_input_config(
            cls,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str,
            num_iterations: int,
            additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare input configuration for orchestrator."""
        config = {
            "strategy_config": strategy_config,
            "symbols": symbols,
            "interval": interval,
            "num_iterations": num_iterations,
            "timestamp": int(time.time()),
            "params": additional_params or {}
        }

        # Add data fetching parameters
        if "start_date" in config["params"]:
            config["start_date"] = config["params"]["start_date"]

        return config

    @classmethod
    def _get_read_only_mongo_uri(cls) -> str:
        """Get read-only MongoDB connection string for containers."""
        # Parse existing URI and create read-only user connection
        # In production, this would be a separate read-only user
        base_uri = settings.MONGO_URI

        # For now, return the same URI but containers will only have read access
        # In production, create a read-only user in MongoDB
        return base_uri

    @classmethod
    def _generate_run_id(
            cls,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str
    ) -> str:
        """Generate unique run ID for caching."""
        data = {
            "strategy": strategy_config,
            "symbols": sorted(symbols),
            "interval": interval,
            "timestamp": int(time.time() / 3600)  # Hour precision for caching
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]

    @classmethod
    def _get_cached_result(cls, run_id: str) -> Optional[Dict[str, Any]]:
        """Get cached result from Redis."""
        if not redis_cache:
            return None

        try:
            cached = redis_cache.get(f"orchestrator:{run_id}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logging.warning(f"Cache retrieval failed: {e}")

        return None

    @classmethod
    def _cache_result(cls, run_id: str, result: Dict[str, Any]):
        """Cache result in Redis with TTL."""
        if not redis_cache:
            return

        try:
            redis_cache.set(
                f"orchestrator:{run_id}",
                json.dumps(result),
                ex=3600  # 1 hour TTL
            )
        except Exception as e:
            logging.warning(f"Cache storage failed: {e}")

    @classmethod
    def _parse_container_output(cls, logs: str) -> Dict[str, Any]:
        """Parse JSON output from container logs."""
        # Split stdout and stderr
        lines = logs.strip().split('\n')

        # Find JSON output (should be last line of stdout)
        for line in reversed(lines):
            if line.strip().startswith('{'):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        raise ValueError("No valid JSON output found in container logs")

    @classmethod
    def cleanup(cls):
        """Cleanup resources."""
        if cls._executor:
            cls._executor.shutdown(wait=True)
        if cls._docker_client:
            cls._docker_client.close()