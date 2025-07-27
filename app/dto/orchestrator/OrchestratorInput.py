"""
OrchestratorInput.py
──────────────────────────────────────────────────────────────────────────
FastAPI ➜ Docker contract.  No `symbol_data`, plus parallel thread count.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ComponentConfig(BaseModel):
    builtin: Optional[str] = None
    module: Optional[str]  = None
    cls:    Optional[str]  = Field(None, alias="class")
    params: Dict[str, Any] = Field(default_factory=dict)

    @validator("builtin", always=True)
    def _one_of(cls, v, values):
        if not v and not values.get("module"):
            raise ValueError("Specify 'builtin' or 'module'")
        return v


class StrategyParameters(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorInput(BaseModel):
    # core
    strategy: StrategyParameters
    symbols: List[str]
    interval: str
    num_iterations: int = 100

    # timing
    start_date: Optional[str] = None
    end_date:   Optional[str] = None

    # portfolio
    initial_capital:    float = 10000.0
    position_size_pct:  float = 5.0
    max_positions:      int   = 10

    # risk
    tp_ratio: float = 0.1
    sl_ratio: float = 0.05

    # plug-ins
    fee_model:      ComponentConfig = Field(default_factory=lambda: {"builtin": "static"})
    slippage_model: ComponentConfig = Field(default_factory=lambda: {"builtin": "zero"})
    fill_policy:    ComponentConfig = Field(default_factory=lambda: {"builtin": "AggressiveMarketPolicy"})
    capacity_policy:ComponentConfig = Field(default_factory=lambda: {"builtin": "LegCapacity"})
    sizing_model:   ComponentConfig = Field(default_factory=lambda: {"builtin": "fixed_fraction"})

    # exec
    parallel_symbols: int = 4
    use_perpetuals:   bool = False
    save_charts:      bool = False
    custom_strategy_code: Optional[str] = None

    @validator("interval")
    def _valid_interval(cls, v):
        allowed = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        if v not in allowed:
            raise ValueError(f"interval must be one of {allowed}")
        return v
