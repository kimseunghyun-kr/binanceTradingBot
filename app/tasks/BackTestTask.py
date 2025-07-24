# app/tasks/BackTestTask.py
from datetime import datetime
import logging
import asyncio
from typing import Dict, Any

from pymongo import MongoClient

from app.core.celery_app import celery
from app.core.pydanticConfig import settings
from app.services.BackTestService import BackTestServiceV2

# Initialize synchronous Mongo client for task context (Celery tasks run in separate process)
mongo_sync_client = None
if settings.MONGO_URI:
    mongo_sync_client = MongoClient(settings.MONGO_URI)
    mongo_sync_db = mongo_sync_client[settings.MONGO_DB]

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.BackTestTask.run_backtest_task", bind=True)
def run_backtest_task(self, config: Dict[str, Any]):
    """
    Celery task to execute a backtest. Matches the V2 controller expectations.
    """
    task_id = self.request.id
    
    # Update progress in MongoDB
    def update_progress(progress: int, message: str = "", current_symbol: str = ""):
        if mongo_sync_client:
            try:
                mongo_sync_db["backtest_progress"].update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            "progress": progress,
                            "message": message,
                            "current_symbol": current_symbol,
                            "timestamp": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                # Update Celery task state
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'current': current_symbol,
                        'total': len(config.get("symbols", []))
                    }
                )
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
    
    try:
        # Extract parameters from config
        strategy_name = config.get("strategy_name")
        strategy_params = config.get("strategy_params", {})
        symbols = config.get("symbols", [])
        interval = config.get("interval", "1h")
        num_iterations = config.get("num_iterations", 100)
        start_date = config.get("start_date")
        end_date = config.get("end_date")
        custom_strategy_code = config.get("custom_strategy_code")
        
        # Additional parameters
        use_cache = config.get("use_cache", True)
        save_results = config.get("save_results", True)
        initial_capital = config.get("initial_capital", 10000.0)
        position_size_pct = config.get("position_size_pct", 5.0)
        max_positions = config.get("max_positions", 10)
        tp_ratio = config.get("tp_ratio", 0.1)
        sl_ratio = config.get("sl_ratio", 0.05)
        
        # Execution model parameters
        fee_model = config.get("fee_model")
        slippage_model = config.get("slippage_model")
        fill_policy = config.get("fill_policy")
        
        update_progress(10, "Starting backtest...")
        
        # Convert start/end dates if provided as strings
        if start_date and isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date and isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Run backtest using async service
        # Since Celery task is sync, we need to run async code
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        update_progress(20, "Initializing backtest service...")
        
        results = loop.run_until_complete(
            BackTestServiceV2.run_backtest(
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                symbols=symbols,
                interval=interval,
                num_iterations=num_iterations,
                start_date=start_date,
                end_date=end_date,
                custom_strategy_code=custom_strategy_code,
                parallel_symbols=config.get("parallel_symbols", 4),
                use_cache=use_cache,
                save_results=save_results,
                initial_capital=initial_capital,
                position_size_pct=position_size_pct,
                max_positions=max_positions,
                tp_ratio=tp_ratio,
                sl_ratio=sl_ratio,
                fee_model=fee_model,
                slippage_model=slippage_model,
                fill_policy=fill_policy
            )
        )
        
        update_progress(100, "Backtest completed")
        
        # Store task results
        if mongo_sync_client and save_results:
            try:
                result_doc = {
                    "task_id": task_id,
                    "user_id": config.get("user_id"),
                    "status": "completed",
                    "created_at": datetime.utcnow(),
                    **results
                }
                mongo_sync_db["backtest_results"].update_one(
                    {"task_id": task_id},
                    {"$set": result_doc},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Failed to save results: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"Backtest task failed: {e}")
        update_progress(0, f"Error: {str(e)}")
        
        # Save error to MongoDB
        if mongo_sync_client:
            try:
                mongo_sync_db["backtest_errors"].insert_one({
                    "task_id": task_id,
                    "error": str(e),
                    "config": config,
                    "timestamp": datetime.utcnow()
                })
            except Exception as save_err:
                logger.error(f"Failed to save error: {save_err}")
        
        raise
