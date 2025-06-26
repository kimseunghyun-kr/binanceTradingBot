from fastapi import APIRouter, HTTPException

from app.dto.BackTestAnalysisRequest import BacktestAnalysisRequest
from app.dto.BackTestRequest import BacktestRequest
from app.dto.GridTestRequest import GridSearchRequest
from app.dto.TaskSubmitResponse import TaskSubmitResponse
from app.core import SymbolInitialize as symbol_utils
from app.tasks.GridSearchTask import run_grid_search_task
from app.tasks.BackTestAnalysisTask import run_backtest_analysis_task

router = APIRouter(prefix="/backtest", tags=["Backtest"])

@router.post("", response_model=TaskSubmitResponse)
def start_backtest(request: BacktestRequest):
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for backtest.")
    payload = request.dict()
    payload["symbols"] = symbol_list
    async_result = run_backtest_task.delay(payload)
    return {"task_id": async_result.id, "detail": "Task submitted"}

@router.post("/gridsearch", response_model=TaskSubmitResponse)
def start_grid_search(request: GridSearchRequest):
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for grid search.")
    payload = request.dict()
    payload["symbols"] = symbol_list
    async_result = run_grid_search_task.delay(payload)
    return {"task_id": async_result.id, "detail": "Task submitted"}

@router.post("/analysis", response_model=TaskSubmitResponse)
def start_backtest_analysis(request: BacktestAnalysisRequest):
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for backtest+analysis.")
    payload = request.model_dump()
    payload["symbols"] = symbol_list
    async_result = run_backtest_analysis_task.delay(payload)
    return {"task_id": async_result.id, "detail": "Task submitted"}
