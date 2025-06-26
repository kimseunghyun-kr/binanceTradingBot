from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core import SymbolInitialize as symbol_utils
from app.controller.BacktestController import TaskSubmitResponse
from app.tasks.AnalysisTask import run_analysis_task

router = APIRouter(prefix="", tags=["Analysis"])

class AnalyzeRequest(BaseModel):
    interval: str = "1d"  # '1d' for daily or '1w' for weekly analysis
    symbols: Optional[List[str]] = None

@router.post("/analyze", response_model=TaskSubmitResponse)
def start_analysis(request: AnalyzeRequest):
    """
    Start a market analysis (daily/weekly) for the given interval on the configured symbol list.
    Schedules a Celery task to perform analysis across symbols.
    """
    symbol_list = request.symbols or symbol_utils.ANALYSIS_SYMBOLS
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols available for analysis. Please load symbols first.")
    # Enqueue the analysis task
    async_result = run_analysis_task.delay({"interval": request.interval, "symbols": symbol_list})
    return {"task_id": async_result.id, "detail": "Task submitted"}
