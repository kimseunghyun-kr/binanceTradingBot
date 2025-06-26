from typing import Optional

from app.dto.BackTestRequest import BacktestRequest


class BacktestAnalysisRequest(BacktestRequest):
    analysis_interval: Optional[str] = "1d"
