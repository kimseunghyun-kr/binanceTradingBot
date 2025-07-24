"""
BackTestServiceV2.py
──────────────────────────────────────────────────────────────────────────
FastAPI-side wrapper that spawns sandboxed orchestrator runs.
Now *does not* embed symbol_data and forwards `parallel_symbols`.
"""

import hashlib, json, logging, traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.init_services import redis_cache, get_mongo_client
from app.core.pydanticConfig.settings import get_settings
from app.dto.orchestrator.OrchestratorInput import OrchestratorInput
from app.services.orchestrator.OrchestratorService import OrchestratorService

settings = get_settings()

class BackTestServiceV2:
    # ───────────────────────── public entrypoint ─────────────────────── #
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
                logging.info(f"Cache hit [{cache_key[:16]}]")
                return cached

        orchestrator_input = OrchestratorInput(
            strategy={"name": strategy_name, "params": strategy_params},
            symbols=symbols,
            interval=interval,
            num_iterations=num_iterations,
            start_date=start_date,
            end_date=end_date,
            custom_strategy_code=custom_strategy_code,
            parallel_symbols=parallel_symbols,
            **kwargs
        )

        strategy_code = custom_strategy_code or await cls._get_strategy_code(strategy_name)

        try:
            raw_result = await OrchestratorService.run_backtest(
                strategy_code=strategy_code,
                strategy_config=orchestrator_input.strategy.dict(),
                symbols=symbols,
                interval=interval,
                num_iterations=num_iterations,
                additional_params=orchestrator_input.dict(
                    exclude={"strategy", "symbols", "interval", "num_iterations"}
                ),
            )

            result = await cls._enrich(raw_result, orchestrator_input)

            if use_cache:
                await cls._cache_set(cache_key, result)
            if save_results:
                await cls._save_result(result)

            return result

        except Exception as e:
            logging.error(f"Backtest failed: {e}\n{traceback.format_exc()}")
            err_doc = {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "input": orchestrator_input.dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            if save_results:
                await cls._save_error(err_doc)
            raise

    # ───────────────────────── helper methods ─────────────────────────── #
    @classmethod
    async def _get_strategy_code(cls, name: str) -> str:
        mongo = get_mongo_client()[settings.MONGO_DB]
        doc = await mongo.strategies.find_one({"name": name})
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
            "start": start.isoformat() if start else None,
            "code_hash": (hashlib.md5(custom_code.encode()).hexdigest()
                          if custom_code else None),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @classmethod
    async def _cache_get(cls, key: str) -> Optional[Dict[str, Any]]:
        if not redis_cache:
            return None
        try:
            raw = redis_cache.get(f"backtest:v2:{key}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logging.warning(f"Redis get failed: {e}")
            return None

    @classmethod
    async def _cache_set(cls, key: str, value: Dict[str, Any]):
        if not redis_cache:
            return
        try:
            await redis_cache.set(
                f"backtest:v2:{key}",
                json.dumps(value, default=str),
                ex=7200,
            )
        except Exception as e:
            logging.warning(f"Redis set failed: {e}")

    # ----------------------------------------------------------- mongo -- #
    @classmethod
    async def _save_result(cls, doc: Dict[str, Any]):
        await get_mongo_client()[settings.MONGO_DB].backtest_results.insert_one(
            {**doc, "created_at": datetime.utcnow()}
        )

    @classmethod
    async def _save_error(cls, doc: Dict[str, Any]):
        await get_mongo_client()[settings.MONGO_DB].backtest_errors.insert_one(
            {**doc, "created_at": datetime.utcnow()}
        )

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
