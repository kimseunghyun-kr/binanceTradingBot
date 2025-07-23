"""
GraphQL Type Definitions
──────────────────────────────────────────────────────────────────────────
Strawberry type definitions for GraphQL schema.
"""

import strawberry
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


@strawberry.enum
class TimeFrame(Enum):
    """Supported timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


@strawberry.enum
class StrategyType(Enum):
    """Strategy categories."""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    COMPOSITE = "composite"
    CUSTOM = "custom"


@strawberry.type
class Symbol:
    """Symbol/coin information."""
    symbol: str
    name: str
    market_cap: float
    volume_24h: float
    price: float
    price_change_24h: float
    price_change_7d: Optional[float] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    tags: List[str] = strawberry.field(default_factory=list)
    sector: Optional[str] = None
    exchanges: List[str] = strawberry.field(default_factory=list)
    last_updated: datetime = strawberry.field(default_factory=datetime.utcnow)


@strawberry.input
class SymbolFilter:
    """Filter criteria for symbol queries."""
    symbols: Optional[List[str]] = None
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None
    volume_min: Optional[float] = None
    volume_max: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_change_min: Optional[float] = None
    price_change_max: Optional[float] = None
    tags: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    exchanges: Optional[List[str]] = None

    # Technical indicators
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    sma_above_price: Optional[bool] = None

    # Custom filter expression
    custom_filter: Optional[str] = None


@strawberry.type
class SymbolStats:
    """Detailed symbol statistics."""
    symbol: str
    timeframe: str
    high: float
    low: float
    open: float
    close: float
    volume: float
    trades: int
    volatility: float
    sharpe_ratio: Optional[float] = None
    correlation_btc: Optional[float] = None
    technical_indicators: Optional[Dict[str, float]] = None


@strawberry.type
class StrategyPerformance:
    """Strategy performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: Optional[float] = None
    max_drawdown: float
    recovery_factor: Optional[float] = None
    calmar_ratio: Optional[float] = None


@strawberry.type
class Strategy:
    """Trading strategy information."""
    id: str
    name: str
    description: Optional[str] = None
    type: StrategyType
    parameters: Dict[str, Any]
    required_indicators: List[str] = strawberry.field(default_factory=list)
    performance: Optional[StrategyPerformance] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    version: str = "1.0.0"


@strawberry.input
class StrategyFilter:
    """Filter criteria for strategy queries."""
    name_contains: Optional[str] = None
    type: Optional[StrategyType] = None
    min_win_rate: Optional[float] = None
    max_drawdown: Optional[float] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None


@strawberry.type
class Trade:
    """Individual trade information."""
    id: str
    symbol: str
    side: str  # "buy" or "sell"
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    fees: float = 0.0
    slippage: float = 0.0
    status: str  # "open", "closed", "cancelled"


@strawberry.type
class BacktestResult:
    """Backtest execution result."""
    id: str
    strategy_name: str
    symbols: List[str]
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    trades: List[Trade]
    created_at: datetime
    execution_time_seconds: float

    # Progress tracking for subscriptions
    progress: Optional[float] = None
    current_symbol: Optional[str] = None
    completed_symbols: Optional[List[str]] = None
    estimated_time_remaining: Optional[int] = None


@strawberry.input
class BacktestFilter:
    """Filter criteria for backtest result queries."""
    strategy_name: Optional[str] = None
    symbols: Optional[List[str]] = None
    min_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


@strawberry.type
class MarketMetrics:
    """Overall market metrics."""
    total_market_cap: float
    total_volume_24h: float
    btc_dominance: float
    eth_dominance: float
    defi_tvl: Optional[float] = None
    active_coins: int
    timestamp: datetime

    @strawberry.field
    def top_gainers(self) -> List[Symbol]:
        """Top gaining symbols."""
        return []

    @strawberry.field
    def top_losers(self) -> List[Symbol]:
        """Top losing symbols."""
        return []

    @strawberry.field
    def trending_symbols(self) -> List[Symbol]:
        """Trending symbols based on social/search metrics."""
        return []


@strawberry.type
class QueryExpression:
    """Parsed query expression for advanced filtering."""
    field: str
    operator: str  # >, <, =, !=, contains, in
    value: Any
    logical_operator: Optional[str] = None  # AND, OR
    nested_expressions: Optional[List['QueryExpression']] = None


# Update forward references
QueryExpression.model_rebuild() if hasattr(QueryExpression, 'model_rebuild') else None