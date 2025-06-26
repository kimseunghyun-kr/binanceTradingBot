from fastapi import APIRouter, HTTPException
from app.core import SymbolInitialize as symbol_utils
from app.dto.BackTestRequest import BacktestRequest
from app.dto.TaskSubmitResponse import TaskSubmitResponse
from app.tasks.BackTestTask import run_backtest_task

from app.services.StrategyService import StrategyService

router = APIRouter(prefix="", tags=["Backtest"])  # No prefix, endpoint is /backtest

@router.post("/backtest", response_model=TaskSubmitResponse)
def start_backtest(request: BacktestRequest):
    """
    Start a backtest based on the provided configuration.
    This schedules a Celery task to run the backtest and returns a task ID for tracking.
    """
    # Ensure symbols are available
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for backtest. Please load symbols first.")
    try:
        # Create strategy instance (just for validation; actual strategy logic will run in task)
        StrategyService.get_strategy_instance(request.strategy.name,
                                              {"params": request.strategy.params or {},
                                               "strategies": [s.dict() for s in (request.strategy.strategies or [])]})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Prepare task payload
    task_payload = {
        "strategy_spec": request.strategy.dict(),
        "timeframe": request.timeframe,
        "num_iterations": request.num_iterations,
        "use_cache": request.use_cache,
        "save_charts": request.save_charts,
        "add_buy_pct": request.add_buy_pct,
        "start_date": request.start_date,
        "symbols": symbol_list
    }
    # Enqueue the backtest task
    async_result = run_backtest_task.delay(task_payload)
    return {"task_id": async_result.id, "detail": "Task submitted"}
