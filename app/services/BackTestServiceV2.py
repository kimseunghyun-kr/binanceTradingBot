"""
BackTestServiceV2.py
──────────────────────────────────────────────────────────────────────────
Enhanced backtest service with proper orchestrator integration, custom strategy
support, and improved error handling.
"""

import hashlib
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.db import get_mongo_client, redis_cache
from app.dto.orchestrator.OrchestratorInput import OrchestratorInput, OrchestratorOutput
from app.services.DataService import DataService
from app.services.orchestrator.OrchestratorService import OrchestratorService


class BackTestServiceV2:
    """
    Enhanced backtest service with orchestrator integration.
    
    Features:
    - Custom strategy code support
    - Asynchronous execution
    - Improved caching
    - Result persistence
    - Error recovery
    """
    
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
        use_cache: bool = True,
        save_results: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run a backtest with the specified parameters.
        
        Args:
            strategy_name: Name of the strategy
            strategy_params: Strategy-specific parameters
            symbols: List of symbols to backtest
            interval: Timeframe interval
            num_iterations: Number of iterations
            start_date: Optional start date
            end_date: Optional end date
            custom_strategy_code: Optional custom strategy Python code
            use_cache: Whether to use cached results
            save_results: Whether to save results to database
            **kwargs: Additional parameters
            
        Returns:
            Backtest results dictionary
        """
        # Generate cache key
        cache_key = cls._generate_cache_key(
            strategy_name, strategy_params, symbols, interval,
            num_iterations, start_date, custom_strategy_code
        )
        
        # Check cache
        if use_cache:
            cached_result = await cls._get_cached_result(cache_key)
            if cached_result:
                logging.info(f"Returning cached result for key {cache_key[:16]}")
                return cached_result
        
        # Prepare orchestrator input
        orchestrator_input = OrchestratorInput(
            strategy={
                "name": strategy_name,
                "params": strategy_params
            },
            symbols=symbols,
            interval=interval,
            num_iterations=num_iterations,
            start_date=start_date,
            end_date=end_date,
            custom_strategy_code=custom_strategy_code,
            **kwargs
        )
        
        # Fetch and prepare data
        symbol_data = await cls._prepare_symbol_data(
            symbols, interval, num_iterations, start_date
        )
        
        # Determine strategy code
        strategy_code = custom_strategy_code or await cls._get_strategy_code(strategy_name)
        
        try:
            # Run backtest via orchestrator
            result = await OrchestratorService.run_backtest(
                strategy_code=strategy_code,
                strategy_config=orchestrator_input.strategy.dict(),
                symbols=symbols,
                interval=interval,
                num_iterations=num_iterations,
                additional_params={
                    **orchestrator_input.dict(exclude={'strategy', 'symbols', 'interval', 'num_iterations'}),
                    'symbol_data': symbol_data
                }
            )
            
            # Enrich result
            enriched_result = await cls._enrich_result(result, orchestrator_input)
            
            # Cache result
            if use_cache:
                await cls._cache_result(cache_key, enriched_result)
            
            # Save to database
            if save_results:
                await cls._save_result(enriched_result)
            
            return enriched_result
            
        except Exception as e:
            logging.error(f"Backtest failed: {str(e)}\n{traceback.format_exc()}")
            
            # Create error result
            error_result = {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "input": orchestrator_input.dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Save error for debugging
            if save_results:
                await cls._save_error(error_result)
            
            raise
    
    @classmethod
    async def _prepare_symbol_data(
        cls,
        symbols: List[str],
        interval: str,
        num_iterations: int,
        start_date: Optional[datetime]
    ) -> Dict[str, str]:
        """Fetch and prepare symbol data for backtest."""
        symbol_data = {}
        
        # Use DataService to fetch candles
        for symbol in symbols:
            try:
                df = await DataService.get_candles(
                    symbol=symbol,
                    interval=interval,
                    limit=num_iterations + 200,  # Extra for warmup
                    start_date=start_date
                )
                
                if df is not None and not df.empty:
                    # Convert to JSON for orchestrator
                    symbol_data[symbol] = df.to_json(orient="split", date_format="iso")
                else:
                    logging.warning(f"No data available for {symbol}")
                    
            except Exception as e:
                logging.error(f"Failed to fetch data for {symbol}: {e}")
        
        return symbol_data
    
    @classmethod
    async def _get_strategy_code(cls, strategy_name: str) -> str:
        """Get strategy code from database or filesystem."""
        # First check database for user-uploaded strategies
        mongo_client = get_mongo_client()
        db = mongo_client[settings.MONGO_DB]
        
        strategy_doc = await db.strategies.find_one({"name": strategy_name})
        if strategy_doc and "code" in strategy_doc:
            return strategy_doc["code"]
        
        # Otherwise, load from filesystem (built-in strategies)
        strategy_path = f"entities/strategies/concreteStrategies/{strategy_name}.py"
        try:
            with open(strategy_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise ValueError(f"Strategy '{strategy_name}' not found")
    
    @classmethod
    async def _enrich_result(
        cls,
        raw_result: Dict[str, Any],
        input_config: OrchestratorInput
    ) -> Dict[str, Any]:
        """Enrich orchestrator result with additional metadata."""
        return {
            **raw_result,
            "metadata": {
                "strategy_name": input_config.strategy.name,
                "symbols": input_config.symbols,
                "interval": input_config.interval,
                "num_iterations": input_config.num_iterations,
                "start_date": input_config.start_date.isoformat() if input_config.start_date else None,
                "end_date": input_config.end_date.isoformat() if input_config.end_date else None,
                "timestamp": datetime.utcnow().isoformat()
            },
            "input_config": input_config.dict()
        }
    
    @classmethod
    async def _save_result(cls, result: Dict[str, Any]):
        """Save backtest result to MongoDB."""
        mongo_client = get_mongo_client()
        db = mongo_client[settings.MONGO_DB]
        
        await db.backtest_results.insert_one({
            **result,
            "created_at": datetime.utcnow()
        })
    
    @classmethod
    async def _save_error(cls, error_result: Dict[str, Any]):
        """Save error result for debugging."""
        mongo_client = get_mongo_client()
        db = mongo_client[settings.MONGO_DB]
        
        await db.backtest_errors.insert_one({
            **error_result,
            "created_at": datetime.utcnow()
        })
    
    @classmethod
    def _generate_cache_key(
        cls,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        symbols: List[str],
        interval: str,
        num_iterations: int,
        start_date: Optional[datetime],
        custom_code: Optional[str]
    ) -> str:
        """Generate unique cache key."""
        data = {
            "strategy": strategy_name,
            "params": strategy_params,
            "symbols": sorted(symbols),
            "interval": interval,
            "iterations": num_iterations,
            "start": start_date.isoformat() if start_date else None,
            "code_hash": hashlib.md5(custom_code.encode()).hexdigest() if custom_code else None
        }
        
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()
    
    @classmethod
    async def _get_cached_result(cls, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result from Redis."""
        if not redis_cache:
            return None
            
        try:
            cached = redis_cache.get(f"backtest:v2:{cache_key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logging.warning(f"Cache retrieval failed: {e}")
        
        return None
    
    @classmethod
    async def _cache_result(cls, cache_key: str, result: Dict[str, Any]):
        """Cache result in Redis."""
        if not redis_cache:
            return
            
        try:
            redis_cache.set(
                f"backtest:v2:{cache_key}",
                json.dumps(result, default=str),
                ex=7200  # 2 hours TTL
            )
        except Exception as e:
            logging.warning(f"Cache storage failed: {e}")