import hashlib
import json
import logging
from typing import Dict, Any
from app.core.db import redis_cache

class BacktestService:
    _cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def generate_cache_key(symbols, interval, num_iterations, start_date, strategy_name,
                           tp_ratio, sl_ratio, add_buy_pct, save_charts):
        data = {
            "symbols": sorted(symbols),
            "interval": interval,
            "num_iterations": num_iterations,
            "start_date": start_date or "",
            "strategy": strategy_name,
            "tp": tp_ratio, "sl": sl_ratio, "add_buy_pct": add_buy_pct,
            "save_charts": bool(save_charts)
        }
        key_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    @classmethod
    def run_backtest(cls, strategy_name: str, symbols, fetch_candles_func, interval,
                     num_iterations=100, tp_ratio=0.1, sl_ratio=0.05, save_charts=False,
                     add_buy_pct=5.0, start_date=None,
                     use_cache: bool = True) -> Dict[str, Any]:
        """Refactored: No simulation here—just fetches/prepares/caches and calls orchestrator."""
        cache_key = cls.generate_cache_key(
            symbols, interval, num_iterations, start_date, strategy_name,
            tp_ratio, sl_ratio, add_buy_pct, save_charts
        )

        if use_cache:
            if redis_cache:
                cached_json = redis_cache.get(cache_key)
                if cached_json:
                    logging.info(f"[BacktestService] Returning cached results from Redis for key {cache_key[:8]}...")
                    return json.loads(cached_json)
            if cache_key in cls._cache:
                logging.info(
                    f"[BacktestService] Using cached results for {strategy_name} {interval} on {len(symbols)} symbols.")
                return cls._cache[cache_key]

        # --- Prepare data for orchestrator ---
        symbol_data = {}
        for sym in symbols:
            df = fetch_candles_func(sym, interval, limit=num_iterations + 200)
            symbol_data[sym] = df.to_json(orient="split")

        # Pass all params, symbol_data, strategy_name (strategy code mounted in container)
        orchestrator_input = {
            "symbols": symbols,
            "interval": interval,
            "num_iterations": num_iterations,
            "tp_ratio": tp_ratio,
            "sl_ratio": sl_ratio,
            "add_buy_pct": add_buy_pct,
            "save_charts": save_charts,
            "start_date": start_date,
            "strategy_name": strategy_name,
            "symbol_data": symbol_data
        }
        results = call_strategy_orchestrator(orchestrator_input)
        if use_cache:
            cls._cache[cache_key] = results
            if redis_cache:
                try:
                    redis_cache.set(cache_key, json.dumps(results), ex=3600)
                except Exception as e:
                    logging.error(f"Redis caching failed: {e}")
        return results

def call_strategy_orchestrator(input_config: dict):
    """Spawn orchestrator as Docker container (stdin/stdout) or as a subprocess for local dev."""
    import subprocess
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", "strategy_orchestrator_image"],  # Replace with your image name!
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    out, _ = proc.communicate(json.dumps(input_config).encode())
    return json.loads(out.decode())
