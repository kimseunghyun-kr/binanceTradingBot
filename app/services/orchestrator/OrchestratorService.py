# OrchestratorService.py  (DinD-free 2025-08-01)

from __future__ import annotations

import asyncio
import io
import json
import logging
import tarfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from socket import socket
from typing import Any, Dict, Optional, Container

from celery.utils.log import get_task_logger
from docker.errors import APIError
from docker.types import LogConfig

from app.core.db.mongodb_config import MongoDBConfig
from app.core.init_services import get_redis_cache
from app.core.pydanticConfig.settings import get_settings
from app.dto.orchestrator.OrchestratorInput import OrchestratorInput
from app.services.orchestrator import Docker_Engine  # <─ host daemon only
from app.services.orchestrator.DataPrefetchService import DataPrefetchService

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
            cfg: OrchestratorInput,  # the model
            strategy_code: str,
    ) -> tuple[str, Dict[str, Any]]:
        cls._ensure_ready()

        run_id = cls._generate_run_id(cfg)  # uses signature_json()
        logger.info("OrchestratorService: running backtest %s", run_id)

        if cached := cls._get_cached_result(run_id):
            return cached

        # ═══ PRE-FETCH OHLCV DATA (Pure Function Approach) ═══
        # Fetch all required data on HOST side, so container doesn't need DB access
        logger.info("Pre-fetching OHLCV data for %d symbols", len(cfg.symbols))
        loop = asyncio.get_running_loop()

        # Get strategy lookback requirement
        # We need to load the strategy to get its lookback, but do it safely
        try:
            from strategyOrchestrator.entities.config.registry import STRAT_MAP
            strategy_cfg = cfg.strategy.model_dump()
            strategy_name = strategy_cfg.get("name")
            if strategy_name in STRAT_MAP:
                strategy_cls = STRAT_MAP[strategy_name]
                strategy_instance = strategy_cls()
                lookback = strategy_instance.get_required_lookback()
            else:
                lookback = 200  # Default fallback
        except Exception as e:
            logger.warning(f"Could not determine strategy lookback: {e}, using default 200")
            lookback = 200

        # Pre-fetch data using DataPrefetchService
        prefetch_service = DataPrefetchService(
            mongo_uri=settings.MONGO_URI_SLAVE or MongoDBConfig.get_read_only_uri(),
            db_name=settings.MONGO_DB_OHLCV
        )

        ohlcv_data = await loop.run_in_executor(
            cls._executor,
            prefetch_service.prefetch_ohlcv_data,
            cfg.symbols,
            cfg.interval,
            cfg.num_iterations,
            lookback,
            cfg.start_date,
            cfg.end_date,
            True,  # include_detailed
        )

        logger.info("Pre-fetch complete, assembling container payload")
        input_config = cfg.to_container_payload(ohlcv_data=ohlcv_data)  # Include pre-fetched data

        try:
            result = await loop.run_in_executor(
                cls._executor,
                cls._run_container,
                strategy_code,
                input_config,
                run_id,
            )
        except Exception:
            logger.exception("OrchestratorService: backtest %s failed", run_id)
            raise

        cls._cache_result(run_id, result)
        return run_id, result

    # ───────────────────────── internals ──────────────────────────
    @classmethod
    def _container_config(cls, run_id: str) -> Dict[str, Any]:
        """
        Build a host-daemon container config.

        IMPORTANT: This is now a PURE FUNCTION container config.
        - NO database credentials
        - NO network access (network_mode: none)
        - All data is passed via stdin
        - Container is truly sandboxed
        """
        logger.info(f"OrchestratorService: creating sandboxed container (no DB access)")

        # ═══ PURE FUNCTION ENVIRONMENT (minimal) ═══
        # No database URIs, no credentials, no secrets
        env = {
            "KWONTBOT_MODE": "sandbox_pure",  # New mode for pure function execution
            "PROFILE": "sandbox",
            "PYTHONUNBUFFERED": "1",
        }

        cfg: Dict[str, Any] = {
            "image": Docker_Engine.image_name(),
            "name": f"orchestrator_{run_id[:12]}",
            "command": ["python", "-m", "strategyOrchestrator.StrategyOrchestrator"],
            "environment": env,
            "network_mode": "none",  # ← NO NETWORK ACCESS (fully isolated)
            "mem_limit": "2g",
            "cpu_quota": 100000,
            "log_config": LOG_CFG,
            "tty": False,
            "auto_remove": False,
            "stdin_open": True,
        }

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
    def _generate_run_id(cfg: OrchestratorInput) -> str:
        import hashlib
        return hashlib.sha256(cfg.signature_json().encode()).hexdigest()[:16]

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
