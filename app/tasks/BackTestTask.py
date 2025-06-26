from pymongo import MongoClient
from datetime import datetime
from app.core.celery_app import celery
from app.pydanticConfig.settings import settings
from app.services.StrategyService import StrategyService
from app.services.BackTestService import BacktestService

# Use PyMongo for Mongo operations in Celery (Celery tasks are not async)
mongo_sync_client = None
if settings.MONGO_URI:
    mongo_sync_client = MongoClient(settings.MONGO_URI)
    mongo_sync_db = mongo_sync_client[settings.MONGO_DATABASE]

@celery.task(name="app.tasks.backtest.run_backtest_task")
def run_backtest_task(config: dict):
    """
    Celery task to execute a backtest.
    `config` is a dict containing strategy specification and backtest parameters.
    """
    strategy_spec = config.get("strategy_spec", {})
    try:
        # Create strategy instance from spec
        strat = StrategyService.get_strategy_instance(strategy_spec["name"],
                                                     {"params": strategy_spec.get("params", {}),
                                                      "strategies": strategy_spec.get("strategies", [])})
    except Exception as e:
        # If strategy instantiation fails, log and abort
        return {"error": str(e)}
    # Run backtest using the service
    results = BacktestService.run_backtest(
        strat,
        symbols=config.get("symbols", []),
        interval=config.get("timeframe"),
        num_iterations=config.get("num_iterations", 100),
        tp_ratio=strategy_spec.get("params", {}).get("tp_ratio", 0.1),
        sl_ratio=strategy_spec.get("params", {}).get("sl_ratio", 0.05),
        save_charts=config.get("save_charts", False),
        add_buy_pct=config.get("add_buy_pct", 5.0),
        start_date=config.get("start_date")
    )
    # Store result in MongoDB for later retrieval
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
            # Log to console if unable to save (since no direct user response here)
            print(f"[BacktestTask] MongoDB insert failed: {e}")
    # (Optionally, one could also store summary in Postgres if needed)
    # Return a short summary (not the full results to avoid large data in broker)
    summary = {
        "total_trades": len(results.get("trades", [])),
        "win_rate": results.get("win_rate"),
        "total_return_pct": results.get("total_return_pct")
    }
    return summary
