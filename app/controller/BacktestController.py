from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.core import SymbolInitialize as symbol_utils
from app.tasks.BackTestTask import run_backtest_task

from app.services.StrategyService import StrategyService

router = APIRouter(prefix="", tags=["Backtest"])  # No prefix, endpoint is /backtest

# Pydantic models for request and response
class SubStrategySpec(BaseModel):
    name: str
    weight: Optional[float] = 1.0
    params: Optional[Dict[str, Any]] = None

class StrategySpec(BaseModel):
    name: str = Field(..., description="Strategy name (e.g., 'peak_ema_reversal', 'momentum', or 'ensemble')")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters for the strategy")
    strategies: Optional[List[SubStrategySpec]] = Field(None, description="If name='ensemble', list of sub-strategies")

class BacktestRequest(BaseModel):
    strategy: StrategySpec
    timeframe: str = Field(..., alias="timeframe", description="Timeframe for backtest (e.g., '1d' or '1w')")
    num_iterations: int = 100
    use_cache: bool = False
    save_charts: bool = False
    add_buy_pct: float = 5.0
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD) for backtest")
    symbols: Optional[List[str]] = Field(None, description="List of symbols to backtest. If omitted, uses the filtered symbol list.")

class TaskSubmitResponse(BaseModel):
    task_id: str
    detail: str = "Task submitted"

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
