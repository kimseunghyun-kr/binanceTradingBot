from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

from docker.types import LogConfig

from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import get_redis_cache
from app.core.pydanticConfig.settings import get_settings
from app.services.orchestrator import Docker_Engine
from app.services.orchestrator.Docker_Engine import _compose_network_name, _to_service_uri

settings = get_settings()
LOG_CFG = LogConfig(type="local", config={"max-size": "10m", "max-file": "3"})

class OrchestratorService:
    """
    Manages strategy orchestrator execution in isolated Docker containers.
    """

    _executor: Optional[ThreadPoolExecutor] = None
    _max_concurrent_runs = 5

    # -------------------------------
    # Lifecycle
    # -------------------------------
    @classmethod
    def initialize(cls, *, force_rebuild: bool | None = None) -> None:
        """
            Initialize executor and ensure docker engine/image are ready.
            Safe to call multiple times.
        """
        Docker_Engine.initialize()
        if force_rebuild is None:
            force_rebuild = getattr(settings, "ORCH_REBUILD_ON_START", False)
        Docker_Engine.ensure_orchestrator_image(force_rebuild=force_rebuild)

        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=cls._max_concurrent_runs)
            logging.info("OrchestratorService: executor initialized.")

    @classmethod
    def _ensure_ready(cls) -> None:
        if cls._executor is None:
            cls.initialize()

    # -------------------------------
    # Public API
    # -------------------------------
    @classmethod
    async def run_backtest(
        cls,
        strategy_code: str,
        strategy_config: Dict[str, Any],
        symbols: List[str],
        interval: str,
        num_iterations: int,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cls._ensure_ready()

        run_id = cls._generate_run_id(strategy_config, symbols, interval)

        if cached_result := cls._get_cached_result(run_id):
            return cached_result

        input_config = cls._prepare_input_config(
            strategy_config, symbols, interval, num_iterations, additional_params
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            cls._executor,
            cls._run_container,
            strategy_code,
            input_config,
            run_id,
        )

        cls._cache_result(run_id, result)
        return result

    # -------------------------------
    # Internals
    # -------------------------------
    @classmethod
    def _container_config(cls, strategy_file: str, run_id: str) -> Dict[str, Any]:
        net = _compose_network_name()

        master_uri = _to_service_uri(settings.MONGO_URI_MASTER, "mongo", 27017, None)
        slave_uri = _to_service_uri(settings.MONGO_URI_SLAVE, "mongo", 27018, None)

        cfg: Dict[str, Any] = {
            "image": Docker_Engine.image_name(),  # ← changed
            "command": ["python", "-m", "strategyOrchestrator.StrategyOrchestrator"],
            "environment": {
                "MONGO_URI_MASTER": settings.MONGO_URI_MASTER,
                "MONGO_URI_SLAVE": settings.MONGO_URI_SLAVE or "",
                "MONGO_AUTH_ENABLED": "1" if settings.MONGO_AUTH_ENABLED else "0",
                "MONGO_USER_PW": settings.MONGO_USER_PW or "",
                "MONGO_DB_APP": settings.MONGO_DB_APP,
                "MONGO_DB_OHLCV": settings.MONGO_DB_OHLCV or "",
                "MONGO_DB_PERP": settings.MONGO_DB_PERP or "",
                "KWONTBOT_MODE": "sandbox",
                "PROFILE": settings.PROFILE,
                "SECRET_KEY": settings.SECRET_KEY,
            },
            "volumes": {
                strategy_file: {
                    "bind": "/orchestrator/user_strategies/user_strategy.py",
                    "mode": "ro",
                }
            },
            "mem_limit": "2g",
            "cpu_quota": 100000,
            "log_config": LOG_CFG,
        }

        if net:
            cfg["network"] = net
        else:
            # Fallback when not on compose network: talk to host’s published ports
            cfg.setdefault("extra_hosts", {})["host.docker.internal"] = "host-gateway"
            cfg["environment"]["MONGO_URI_MASTER"] = settings.MONGO_URI_MASTER.replace(
                "localhost", "host.docker.internal"
            )
            if settings.MONGO_URI_SLAVE:
                cfg["environment"]["MONGO_URI_SLAVE"] = settings.MONGO_URI_SLAVE.replace(
                    "localhost", "host.docker.internal"
                )

        return cfg

    @classmethod
    def _run_container(
        cls,
        strategy_code: str,
        input_config: Dict[str, Any],
        run_id: str,
    ) -> Dict[str, Any]:
        client = Docker_Engine.client()  # ← get client here

        with tempfile.TemporaryDirectory() as temp_dir:
            strategy_file = os.path.join(temp_dir, "user_strategy.py")
            with open(strategy_file, "w") as f:
                f.write(strategy_code)

            container_config = cls._container_config(strategy_file, run_id)

            container = None
            try:
                container = client.containers.create(**container_config)
                stdin_socket = container.attach_socket(params={"stdin": 1, "stream": 1})
                stdin_socket._sock.send(json.dumps(input_config).encode() + b"\n")
                stdin_socket.close()

                container.start()
                result = container.wait()
                logs = container.logs(stdout=True, stderr=True).decode()

                if result["StatusCode"] == 0:
                    return cls._parse_container_output(logs)
                raise RuntimeError(f"Container exited with code {result['StatusCode']}: {logs}")

            except Exception as e:
                logging.error(f"Container execution failed for run {run_id}: {e}")
                raise
            finally:
                if container is not None:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

    @classmethod
    def _prepare_input_config(
        cls,
        strategy_config: Dict[str, Any],
        symbols: List[str],
        interval: str,
        num_iterations: int,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        config = {
            "strategy_config": strategy_config,
            "symbols": symbols,
            "interval": interval,
            "num_iterations": num_iterations,
            "timestamp": str(int(time.time())),
            "params": additional_params or {},
        }
        if "start_date" in config["params"]:
            config["start_date"] = config["params"]["start_date"]
        return config

    @classmethod
    def _get_read_only_mongo_uri(cls) -> str:
        try:
            return MongoDBConfig.get_read_only_uri()
        except RuntimeError:
            logging.warning("MongoDB config not initialized, using fallback URI")
            if settings.MONGO_URI_SLAVE:
                return settings.MONGO_URI_SLAVE
            return settings.MONGO_URI_MASTER

    @classmethod
    def _generate_run_id(
        cls,
        strategy_config: Dict[str, Any],
        symbols: List[str],
        interval: str,
    ) -> str:
        data = {
            "strategy": strategy_config,
            "symbols": sorted(symbols),
            "interval": interval,
            "timestamp": int(time.time() / 3600),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    @classmethod
    def _get_cached_result(cls, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            redis_cache = get_redis_cache()
            cached = redis_cache.get(f"orchestrator:{run_id}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logging.warning(f"Cache retrieval failed: {e}")
        return None

    @classmethod
    def _cache_result(cls, run_id: str, result: Dict[str, Any]) -> None:
        try:
            redis_cache = get_redis_cache()
            redis_cache.set(f"orchestrator:{run_id}", json.dumps(result), ex=3600)
        except Exception as e:
            logging.warning(f"Cache storage failed: {e}")

    @classmethod
    def _parse_container_output(cls, logs: str) -> Dict[str, Any]:
        for line in reversed(logs.strip().split("\n")):
            s = line.strip()
            if s.startswith("{"):
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    continue
        raise ValueError("No valid JSON output found in container logs")

    @classmethod
    def cleanup(cls) -> None:
        if cls._executor:
            cls._executor.shutdown(wait=True)
            cls._executor = None
