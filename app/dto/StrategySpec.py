from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from app.dto.SubStrategySpec import SubStrategySpec


class StrategySpec(BaseModel):
    name: str = Field(..., description="Strategy name (e.g., 'peak_ema_reversal', 'momentum', or 'ensemble')")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters for the strategy")
    strategies: Optional[List[SubStrategySpec]] = Field(None, description="If name='ensemble', list of sub-strategies")
