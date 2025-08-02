# OrchestratorService.py  (DinD-free 2025-08-01)

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from socket import socket
from typing import Any, Dict, List, Optional, Container

from celery.utils.log import get_task_logger
from docker.types import LogConfig
from docker.errors import APIError

from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import get_redis_cache
from app.core.pydanticConfig.settings import get_settings
from app.services.orchestrator import Docker_Engine  # <─ host daemon only

settings = get_settings()
LOG_CFG = LogConfig(type="local", config={"max-size": "10m", "max-file": "3"})
logger = get_task_logger(__name__)
logger.setLevel(logging.DEBUG)


class OrchestratorService:
    """Runs each strategy orchestrator in a disposable Docker container (no DinD)."""

    _executor: Optional[ThreadPoolExecutor] = None
    _max_concurrent_runs = 5

    # ───────────────────────── lifecycle ──────────────────────────
    @classmethod
    def initialize(cls, *, force_rebuild: bool | None = None) -> None:
        Docker_Engine.initialize()
        if force_rebuild is None:
            force_rebuild = getattr(settings, "ORCH_REBUILD_ON_START", False)
        Docker_Engine.ensure_orchestrator_image(force_rebuild=force_rebuild)

        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=cls._max_concurrent_runs)
            logger.info("OrchestratorService: executor initialized.")

    @classmethod
    def _ensure_ready(cls) -> None:
        if cls._executor is None:
            cls.initialize()

    # ───────────────────────── public API ─────────────────────────
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
        logger.info(f"OrchestratorService: running backtest {run_id}")

        if cached_result := cls._get_cached_result(run_id):
            return cached_result

        input_config = cls._prepare_input_config(
            strategy_config, symbols, interval, num_iterations, additional_params
        )

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                cls._executor, cls._run_container, strategy_code, input_config, run_id
            )
        except Exception as e:
            logger.error(f"OrchestratorService: backtest {run_id} failed: {e}")
            raise

        cls._cache_result(run_id, result)
        return result

    # ───────────────────────── internals ──────────────────────────
    @classmethod
    def _container_config(cls, run_id: str) -> Dict[str, Any]:
        """
        Build a host-daemon container config.
        DinD branch *removed* – we always join the outer Compose network.
        """
        net = Docker_Engine._compose_network_name()
        logger.info(f"OrchestratorService: using network '{net}'")

        # Mongo URIs rewritten to service names (mongo2 only)
        ro_uri = MongoDBConfig.get_read_only_uri().replace("localhost", "mongo2")
        slave_uri = settings.MONGO_URI_SLAVE.replace("localhost", "mongo2")

        env = {
            "KWONTBOT_MODE": "sandbox",
            "PROFILE": settings.PROFILE,
            "SECRET_KEY": settings.SECRET_KEY,
            "MONGO_RO_URI": ro_uri,
            "MONGO_URI_SLAVE": slave_uri or "",
            "MONGO_AUTH_ENABLED": "1" if settings.MONGO_AUTH_ENABLED else "0",
            "MONGO_USER_PW": settings.MONGO_USER_PW or "",
            "MONGO_DB_APP": settings.MONGO_DB_APP,
            "MONGO_DB_OHLCV": settings.MONGO_DB_OHLCV or "",
            "MONGO_DB_PERP": settings.MONGO_DB_PERP or "",
            "DOCKER_NETWORK": net or "",
            "PYTHONUNBUFFERED": 1
        }

        cfg: Dict[str, Any] = {
            "image": Docker_Engine.image_name(),
            "name": f"orchestrator_{run_id[:12]}",
            "command": ["python", "-m", "strategyOrchestrator.StrategyOrchestrator"],
            "environment": env,
            "mem_limit": "2g",
            "cpu_quota": 100000,
            "log_config": LOG_CFG,
            "tty": False,
            "auto_remove": False,
            "stdin_open": True,
        }

        if net:  # always join the Compose bridge
            cfg["network"] = net

        return cfg

    @classmethod
    def _run_container(
            cls,
            strategy_code: str,
            input_config: Dict[str, Any],
            run_id: str,
    ) -> Dict[str, Any]:
        client = Docker_Engine.client()
        container: Container | None = None
        try:
            container_cfg = cls._container_config(run_id)

            # --- Ensure stdin is open and Python inside is unbuffered ---
            container_cfg.setdefault("stdin_open", True)
            container_cfg.setdefault("tty", False)
            # Normalize environment to dict for easier mutation
            env = container_cfg.get("environment")
            if isinstance(env, list):
                # convert list like ["A=1", "B=2"] into dict
                env_dict = {}
                for entry in env:
                    if "=" in entry:
                        k, v = entry.split("=", 1)
                        env_dict[k] = v
                env = env_dict
            if not isinstance(env, dict):
                env = {}
            env.setdefault("PYTHONUNBUFFERED", "1")
            container_cfg["environment"] = env

            container = client.containers.create(**container_cfg)
            container.start()

            # Upload user strategy if present
            if strategy_code.strip():
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode="w") as tar:
                    data = strategy_code.encode()
                    info = tarfile.TarInfo("user_strategies/user_strategy.py")
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                buf.seek(0)
                container.put_archive("/orchestrator", buf.read())
                input_config["strategy_filename"] = "user_strategy.py"

            # Feed orchestrator its JSON, ensuring EOF is delivered
            sock = container.attach_socket(params={"stdin": 1, "stream": 1})
            try:
                payload = json.dumps(input_config) + "\n"
                logger.info("json dumped is %s", payload)

                # Prefer high-level write if available
                wrote = False
                if hasattr(sock, "write"):
                    try:
                        sock.write(payload.encode("utf-8"))
                        try:
                            sock.flush()
                        except Exception:
                            pass
                        wrote = True
                    except Exception as e:
                        logger.warning("High-level socket write failed: %s", e)
                if not wrote:
                    raw_sock = getattr(sock, "_sock", None)
                    if raw_sock is None:
                        raise RuntimeError("Cannot find underlying socket to send payload")
                    raw_sock.sendall(payload.encode("utf-8"))
                    try:
                        raw_sock.shutdown(socket.SHUT_WR)
                    except Exception:
                        pass

                # Try to signal EOF on underlying socket if possible
                try:
                    if hasattr(sock, "_sock"):
                        sock._sock.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

            finally:
                # ensure closure (double safety)
                try:
                    if hasattr(sock, "_sock"):
                        sock._sock.shutdown(socket.SHUT_WR)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass

            # --- Explicit wait with timeout so analyzer sees all branches ---
            def _wait_container():
                return container.wait()

            with ThreadPoolExecutor(1) as ex:
                future = ex.submit(_wait_container)
                try:
                    wait_result = future.result(timeout=60)  # enforce 60s startup/backtest bound
                except TimeoutError as e:
                    partial_logs = container.logs(tail=500).decode("utf-8", "replace")
                    raise RuntimeError(
                        f"Container wait timed out after 60s. Partial logs:\n{partial_logs}"
                    ) from e
                except APIError as e:
                    partial_logs = container.logs(tail=500).decode("utf-8", "replace")
                    raise RuntimeError(
                        f"Container wait API error ({e}). Partial logs:\n{partial_logs}"
                    ) from e
                except Exception as e:
                    partial_logs = container.logs(tail=500).decode("utf-8", "replace")
                    raise RuntimeError(
                        f"Container wait failed unexpectedly ({e}). Partial logs:\n{partial_logs}"
                    ) from e

            full_logs = container.logs(stdout=True, stderr=True).decode("utf-8", "replace")
            status = wait_result.get("StatusCode", 1)
            if status == 0:
                tail = container.logs(tail=200).decode("utf-8", "replace")
                logger.info(
                    "OrchestratorService: backtest %s finished\n%s", run_id, tail
                )
                return cls._parse_container_output(full_logs)
            else:
                raise RuntimeError(f"Container exited {status}: {full_logs}")

        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    import time
    from typing import Any, Dict, List, Optional

    @classmethod
    def _prepare_input_config(
            cls,
            strategy_config: Dict[str, Any],
            symbols: List[str],
            interval: str,
            num_iterations: int,
            additional_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        # 1. Merge any additional params up front.
        flat_params = (additional_params or {}).copy()

        # 2. Build the top-level payload.
        config: Dict[str, Any] = {
            "strategy_config": strategy_config,
            "symbols": symbols,
            "interval": interval,
            "num_iterations": num_iterations,
            "timestamp": str(int(time.time())),
            **flat_params,  # ← everything flattened here
        }

        # 3. Convenience: hoist start_date / end_date separately if provided.
        if "start_date" in flat_params:
            config["start_date"] = flat_params["start_date"]
        if "end_date" in flat_params:
            config["end_date"] = flat_params["end_date"]

        return config

    @staticmethod
    def _parse_container_output(logs: str) -> Dict[str, Any]:
        for line in reversed(logs.strip().split("\n")):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise ValueError("No JSON found in orchestrator logs")

    @staticmethod
    def _generate_run_id(cfg: Dict[str, Any], symbols: List[str], interval: str) -> str:
        data = {
            "strategy": cfg,
            "symbols": sorted(symbols),
            "interval": interval,
            "ts": int(time.time() / 3600),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    @staticmethod
    def _get_cached_result(run_id: str) -> Optional[Dict[str, Any]]:
        try:
            rc = get_redis_cache()
            if raw := rc.get(f"orchestrator:{run_id}"):
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
        return None

    @staticmethod
    def _cache_result(run_id: str, result: Dict[str, Any]) -> None:
        try:
            rc = get_redis_cache()
            rc.set(f"orchestrator:{run_id}", json.dumps(result), ex=3600)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
