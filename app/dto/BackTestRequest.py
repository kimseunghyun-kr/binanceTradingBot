from typing import Optional, List

from pydantic import BaseModel

from app.dto import StrategySpec


class BacktestRequest(BaseModel):
    strategy: StrategySpec
    timeframe: str = "1d"
    num_iterations: int = 100
    use_cache: bool = False
    save_charts: bool = False
    add_buy_pct: float = 5.0
    start_date: Optional[str] = None
    symbols: Optional[List[str]] = None