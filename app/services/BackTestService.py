"""
BackTestServiceV2.py
──────────────────────────────────────────────────────────────────────────
FastAPI-side wrapper that spawns sandboxed orchestrator runs.
Now *does not* embed symbol_data and forwards `parallel_symbols`.
"""

import hashlib
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import anyio
from celery.utils.log import get_task_logger

from app.core.init_services import get_redis_cache, master_db_app_async
from app.core.pydanticConfig.settings import get_settings
from app.dto.orchestrator.OrchestratorInput import OrchestratorInput
from app.services.orchestrator.OrchestratorService import OrchestratorService

settings = get_settings()
logger = get_task_logger(__name__)
print(logger.name)
logger.setLevel(logging.DEBUG)


class BackTestServiceV2:
    # ───────────────────────── public entrypoint ─────────────────────── #

    @classmethod
    async def _fetch_strategy_code(
            cls, name: str, custom_code: Optional[str]
    ) -> str:
        """Return either the provided custom code or code fetched from DB."""

        if custom_code:
            return custom_code
        return await cls._get_strategy_code(name)

    @classmethod
    async def _run_orchestrator(
            cls, cfg: OrchestratorInput, code: str
    ) -> Dict[str, Any]:
        """Execute orchestrator and return raw result."""

        return await OrchestratorService.run_backtest(
            strategy_code=code,
            strategy_config=cfg.strategy.dict(),
            symbols=cfg.symbols,
            interval=cfg.interval,
            num_iterations=cfg.num_iterations,
            additional_params=cfg.dict(
                exclude={"strategy", "symbols", "interval", "num_iterations"}
            ),
        )

    @classmethod
    async def run_backtest(
        cls,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        symbols: List[str],
        interval: str = "1h",
        num_iterations: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        custom_strategy_code: Optional[str] = None,
        parallel_symbols: int = 4,
        use_cache: bool = True,
        save_results: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:

        cache_key = cls._cache_key(
            strategy_name, strategy_params, symbols, interval,
            num_iterations, start_date, custom_strategy_code
        )

        if use_cache:
            cached = await cls._cache_get(cache_key)
            if cached:
                logger.info(f"Cache hit [{cache_key[:16]}]")
                return cached

        logger.info(f"Cache miss [{cache_key[:16]}] and the orchestrator input is reached")
        orchestrator_input = OrchestratorInput(
            strategy={"name": strategy_name, "params": strategy_params},
            symbols=symbols,
            interval=interval,
            num_iterations=num_iterations,
            start_date=start_date,
            end_date=end_date,
            custom_strategy_code=custom_strategy_code,
            parallel_symbols=parallel_symbols,
            **kwargs,
        )

        strategy_code = await cls._fetch_strategy_code(strategy_name, custom_strategy_code)

        try:
            raw_result = await cls._run_orchestrator(orchestrator_input, strategy_code)
            logger.error(f"Backtest finished [{raw_result}]")

            result = await cls._enrich(raw_result, orchestrator_input)

            if use_cache:
                await cls._cache_set(cache_key, result)
            if save_results:
                await cls._save_result(result)

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}\n{traceback.format_exc()}")
            err_doc = {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "input": orchestrator_input.dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            if save_results:
                cls.save_error_sync(err_doc)
            raise

    # ───────────────────────── helper methods ─────────────────────────── #
    @classmethod
    async def _get_strategy_code(cls, name: str) -> str:
        mongo_db = master_db_app_async()
        doc = await mongo_db.strategies.find_one({"name": name})
        if doc and "code" in doc:
            return doc["code"]
        path = f"entities/strategies/concreteStrategies/{name}.py"
        try:
            with open(path, "r") as f:
                return f.read()
        except FileNotFoundError:
            raise ValueError(f"Strategy '{name}' not found")

    # ----------------------------------------------------------- cache -- #
    @classmethod
    def _cache_key(
        cls,
        name: str, params: Dict[str, Any], symbols: List[str],
        interval: str, iters: int, start: Optional[datetime],
        custom_code: Optional[str],
    ) -> str:
        data = {
            "strategy": name,
            "params": params,
            "symbols": sorted(symbols),
            "interval": interval,
            "iters": iters,
            "start": start,
            "code_hash": (hashlib.md5(custom_code.encode()).hexdigest()
                          if custom_code else None),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @classmethod
    async def _cache_get(cls, key: str) -> Optional[Dict[str, Any]]:
        try:
            redis_cache = get_redis_cache()
            raw = redis_cache.get(f"backtest:v2:{key}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    @classmethod
    async def _cache_set(cls, key: str, value: Dict[str, Any]):
        try:
            redis_cache = get_redis_cache()
            await redis_cache.set(
                f"backtest:v2:{key}",
                json.dumps(value, default=str),
                ex=7200,
            )
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    # ----------------------------------------------------------- mongo -- #
    @classmethod
    async def _save_result(cls, doc: Dict[str, Any]):
        mongo_db = master_db_app_async()
        await mongo_db.backtest_results.insert_one(
            {**doc, "created_at": datetime.utcnow()}
        )

    @classmethod
    async def _save_error(cls, doc: Dict[str, Any]):
        mongo_db = master_db_app_async()
        await mongo_db.backtest_errors.insert_one(
            {**doc, "created_at": datetime.utcnow()}
        )

    def save_error_sync(cls, doc: Dict[str, Any]):
        anyio.from_thread.run(cls._save_error, doc)  # repo.save_error is async

    # -------------------------------------------------------- enrich ---- #
    @classmethod
    async def _enrich(cls, raw: Dict[str, Any], cfg: OrchestratorInput) -> Dict[str, Any]:
        return {
            **raw,
            "metadata": {
                "strategy": cfg.strategy.name,
                "symbols": cfg.symbols,
                "interval": cfg.interval,
                "num_iterations": cfg.num_iterations,
                "start_date": cfg.start_date.isoformat() if cfg.start_date else None,
                "end_date": cfg.end_date.isoformat()   if cfg.end_date   else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
            "input_config": cfg.dict(),
        }
