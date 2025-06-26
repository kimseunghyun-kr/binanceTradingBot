from typing import List, Optional

from pydantic import BaseModel

from app.dto.StrategySpec import StrategySpec


class GridSearchRequest(BaseModel):
    strategy: StrategySpec
    timeframe: str = "1d"
    tp_list: List[float]
    sl_list: List[float]
    add_buy_pct_list: List[float]
    num_iterations: int = 100
    use_cache: bool = False
    save_charts: bool = False
    start_date: Optional[str] = None
    symbols: Optional[List[str]] = None
