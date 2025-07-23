from fastapi import APIRouter, HTTPException

from app.core import SymbolInitialize as symbol_utils
from app.dto.GridTestRequest import GridSearchRequest
from app.dto.TaskSubmitResponse import TaskSubmitResponse
from app.tasks.GridSearchTask import run_grid_search_task

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/gridsearch", response_model=TaskSubmitResponse)
def start_grid_search(request: GridSearchRequest):
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for grid search.")
    payload = request.dict()
    payload["symbols"] = symbol_list
    async_result = run_grid_search_task.delay(payload)
    return {"task_id": async_result.id, "detail": "Task submitted"}

