from fastapi import APIRouter, HTTPException
from app.core import SymbolInitialize as symbol_utils
from app.dto.BackTestRequest import BacktestRequest
from app.dto.TaskSubmitResponse import TaskSubmitResponse
from app.services.StrategyService import StrategyService
from app.services.SymbolService import SymbolService
from app.tasks.BackTestTask import run_backtest_task

import json

router = APIRouter(prefix="", tags=["Backtest"])

@router.post("/backtest", response_model=TaskSubmitResponse)
def start_backtest(request: BacktestRequest):
    """
    Start a backtest based on the provided configuration.
    This schedules a Celery task to run the backtest and returns a task ID for tracking.
    """
    # 1. Support both symbol list and symbol_criteria
    if request.symbols:
        symbol_list = request.symbols
    elif getattr(request, "symbol_criteria", None):
        criteria = request.symbol_criteria
        # Use your SymbolService to get a pre-filtered universe DataFrame
        symbols_df = SymbolService.get_symbols_by_market_cap(
            min_cap=criteria.get("min_market_cap", 0),
            max_cap=criteria.get("max_market_cap", 2e10),
            max_pages=criteria.get("max_pages", 3),
            api_key=criteria.get("api_key", None),
        )
        # Validate the strategy instance (as before)
        strat = StrategyService.get_strategy_instance(
            request.strategy.name,
            {"params": request.strategy.params or {},
             "strategies": [s.dict() for s in (request.strategy.strategies or [])]}
        )
        # Run the code-based filter (e.g., user’s filter_symbols)
        symbol_list = strat.filter_symbols(symbols_df)
    else:
        symbol_list = symbol_utils.ANALYSIS_SYMBOLS

    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for backtest. Please load symbols first.")

    # Validate strategy as before
    try:
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
