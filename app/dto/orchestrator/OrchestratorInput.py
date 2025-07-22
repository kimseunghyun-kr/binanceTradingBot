"""
OrchestratorInput.py
──────────────────────────────────────────────────────────────────────────
Pydantic models for orchestrator input/output contract.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from pydantic import BaseModel, Field, validator


class StrategyParameters(BaseModel):
    """Parameters for strategy execution."""
    name: str = Field(..., description="Strategy name")
    params: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific parameters")
    
    # For composite strategies
    sub_strategies: Optional[List['StrategyParameters']] = Field(None, description="Sub-strategies for composite patterns")


class FillPolicyConfig(BaseModel):
    """Fill policy configuration."""
    name: str = Field("AggressiveMarketPolicy", description="Fill policy name")
    params: Dict[str, Any] = Field(default_factory=dict, description="Policy parameters")


class FeeModelConfig(BaseModel):
    """Fee model configuration."""
    type: str = Field("static", description="Fee model type: static, per_symbol, dynamic")
    params: Dict[str, Union[float, Dict[str, float]]] = Field(
        default_factory=dict,
        description="Fee parameters"
    )


class SlippageModelConfig(BaseModel):
    """Slippage model configuration."""
    type: str = Field("random", description="Slippage model type: random, fixed, dynamic")
    params: Dict[str, float] = Field(default_factory=dict, description="Slippage parameters")


class OrchestratorInput(BaseModel):
    """Complete input specification for orchestrator execution."""
    
    # Core parameters
    strategy: StrategyParameters = Field(..., description="Strategy configuration")
    symbols: List[str] = Field(..., description="List of symbols to backtest")
    interval: str = Field(..., description="Timeframe interval (1h, 15m, etc)")
    num_iterations: int = Field(100, description="Number of candles to process")
    
    # Timing
    start_date: Optional[datetime] = Field(None, description="Backtest start date")
    end_date: Optional[datetime] = Field(None, description="Backtest end date")
    
    # Portfolio parameters
    initial_capital: float = Field(10000.0, description="Initial capital")
    position_size_pct: float = Field(5.0, description="Position size as % of capital")
    max_positions: int = Field(10, description="Maximum concurrent positions")
    
    # Risk management
    tp_ratio: float = Field(0.1, description="Take profit ratio")
    sl_ratio: float = Field(0.05, description="Stop loss ratio")
    
    # Execution models
    fill_policy: FillPolicyConfig = Field(default_factory=FillPolicyConfig)
    fee_model: FeeModelConfig = Field(default_factory=FeeModelConfig)
    slippage_model: SlippageModelConfig = Field(default_factory=SlippageModelConfig)
    
    # Features
    use_perpetuals: bool = Field(False, description="Use perpetual futures instead of spot")
    save_charts: bool = Field(False, description="Generate and save charts")
    
    # Custom strategy code (optional)
    custom_strategy_code: Optional[str] = Field(None, description="Custom strategy Python code")
    
    @validator('interval')
    def validate_interval(cls, v):
        valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        if v not in valid_intervals:
            raise ValueError(f"Invalid interval. Must be one of: {valid_intervals}")
        return v
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if not v:
            raise ValueError("At least one symbol must be provided")
        return v


class OrchestratorOutput(BaseModel):
    """Output specification from orchestrator execution."""
    
    # Execution metadata
    run_id: str = Field(..., description="Unique run identifier")
    start_time: datetime = Field(..., description="Execution start time")
    end_time: datetime = Field(..., description="Execution end time")
    duration_seconds: float = Field(..., description="Total execution duration")
    
    # Results
    portfolio_metrics: Dict[str, Any] = Field(..., description="Portfolio performance metrics")
    symbol_metrics: Dict[str, Dict[str, Any]] = Field(..., description="Per-symbol metrics")
    trades: List[Dict[str, Any]] = Field(..., description="All executed trades")
    
    # Performance
    total_return: float = Field(..., description="Total return percentage")
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")
    win_rate: float = Field(..., description="Win rate percentage")
    
    # Errors/warnings
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Any warnings generated")
    
    # Charts (if generated)
    chart_urls: Optional[Dict[str, str]] = Field(None, description="URLs to generated charts")


# Update forward references
StrategyParameters.model_rebuild()