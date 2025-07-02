# app/tasks/BackTestTask.py
from datetime import datetime

from pymongo import MongoClient

from app.core.celery_app import celery
from app.marketDataApi.binance import fetch_candles
from app.pydanticConfig.settings import settings
from app.services.BackTestService import BacktestService
from app.services.StrategyService import StrategyService

# Initialize synchronous Mongo client for task context (Celery tasks run in separate process)
mongo_sync_client = None
if settings.MONGO_URI:
    mongo_sync_client = MongoClient(settings.MONGO_URI)
    mongo_sync_db = mongo_sync_client[settings.MONGO_DATABASE]

print("imported BackTestTask")


@celery.task(name="app.tasks.BackTestTask.run_backtest_task")
def run_backtest_task(config: dict):
    """
    Celery task to execute a backtest. `config` contains strategy spec and backtest parameters.
    """
    strategy_spec = config.get("strategy_spec", {})
    try:
        strat = StrategyService.get_strategy_instance(
            strategy_spec["name"],
            {"params": strategy_spec.get("params", {}), "strategies": strategy_spec.get("strategies", [])}
        )
        # Use symbol list passed in config (already filtered)
        filtered_symbols = config.get("symbols", [])
    except Exception as e:
        return {"error": str(e)}

    # Run backtest using BacktestService, providing the data fetch function
    results = BacktestService.run_backtest(
        strat,
        symbols=filtered_symbols,
        fetch_candles_func=fetch_candles,
        interval=config.get("timeframe"),
        num_iterations=config.get("num_iterations", 100),
        tp_ratio=strategy_spec.get("params", {}).get("tp_ratio", 0.1),
        sl_ratio=strategy_spec.get("params", {}).get("sl_ratio", 0.05),
        save_charts=config.get("save_charts", False),
        add_buy_pct=config.get("add_buy_pct", 5.0),
        start_date=config.get("start_date"),
        use_cache=config.get("use_cache", True)
    )
    # Store detailed results in MongoDB for record (same as before)
    if mongo_sync_client:
        try:
            result_doc = {
                "strategy": strategy_spec,
                "timeframe": config.get("timeframe"),
                "run_at": datetime.utcnow(),
                "results": results
            }
            mongo_sync_db["backtest_results"].insert_one(result_doc)
        except Exception as e:
            print(f"[BacktestTask] MongoDB insert failed: {e}")
    # Return a brief summary for the Celery result (to avoid large data in broker)
    summary = {
        "total_trades": len(results.get("trades", [])),
        "win_rate": results.get("win_rate"),
        "total_return_pct": results.get("total_return_pct")
    }
    return summary
