"""
GraphQL Schema for TradingBot
──────────────────────────────────────────────────────────────────────────
Provides flexible querying capabilities for symbols, strategies, and backtests.
"""

import strawberry
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

from app.graphql.types import (
    Symbol, SymbolFilter, SymbolStats,
    Strategy, StrategyFilter,
    BacktestResult, BacktestFilter,
    MarketMetrics
)
from app.graphql.resolvers import (
    SymbolResolver,
    StrategyResolver,
    BacktestResolver,
    MarketResolver
)


@strawberry.type
class Query:
    """Root GraphQL query type."""

    @strawberry.field
    async def symbols(
        self,
        filter: Optional[SymbolFilter] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Symbol]:
        """
        Query symbols with flexible filtering.

        Example:
        ```graphql
        query {
          symbols(filter: {
            marketCapMin: 1000000,
            marketCapMax: 10000000000,
            volumeMin: 1000000,
            tags: ["defi", "layer1"],
            exchanges: ["binance"]
          }, limit: 50) {
            symbol
            name
            marketCap
            volume24h
            priceChange24h
            tags
          }
        }
        ```
        """
        return await SymbolResolver.get_symbols(filter, limit, offset)

    @strawberry.field
    async def symbol_stats(
        self,
        symbols: List[str],
        timeframe: str = "24h"
    ) -> List[SymbolStats]:
        """
        Get detailed statistics for specific symbols.

        Example:
        ```graphql
        query {
          symbolStats(symbols: ["BTC", "ETH"], timeframe: "7d") {
            symbol
            high
            low
            volume
            trades
            volatility
          }
        }
        ```
        """
        return await SymbolResolver.get_symbol_stats(symbols, timeframe)

    @strawberry.field
    async def strategies(
        self,
        filter: Optional[StrategyFilter] = None
    ) -> List[Strategy]:
        """
        Query available strategies.

        Example:
        ```graphql
        query {
          strategies(filter: {
            type: "momentum",
            minWinRate: 0.6
          }) {
            name
            description
            type
            parameters
            performance {
              winRate
              sharpeRatio
              maxDrawdown
            }
          }
        }
        ```
        """
        return await StrategyResolver.get_strategies(filter)

    @strawberry.field
    async def backtest_results(
        self,
        filter: Optional[BacktestFilter] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[BacktestResult]:
        """
        Query historical backtest results.

        Example:
        ```graphql
        query {
          backtestResults(filter: {
            strategyName: "EMAReversalStrategy",
            minReturn: 0.1,
            dateFrom: "2024-01-01"
          }) {
            id
            strategyName
            symbols
            totalReturn
            sharpeRatio
            maxDrawdown
            trades
            createdAt
          }
        }
        ```
        """
        return await BacktestResolver.get_results(filter, limit, offset)

    @strawberry.field
    async def market_metrics(
        self,
        category: Optional[str] = None
    ) -> MarketMetrics:
        """
        Get overall market metrics.

        Example:
        ```graphql
        query {
          marketMetrics(category: "defi") {
            totalMarketCap
            totalVolume24h
            btcDominance
            topGainers {
              symbol
              priceChange24h
            }
            topLosers {
              symbol
              priceChange24h
            }
          }
        }
        ```
        """
        return await MarketResolver.get_market_metrics(category)

    @strawberry.field
    async def symbol_universe(
        self,
        query: str
    ) -> List[Symbol]:
        """
        Advanced symbol selection using custom query language.

        Supports complex queries like:
        - "market_cap > 1B AND volume_24h > 10M AND sector = 'defi'"
        - "rsi_14 < 30 OR rsi_14 > 70"
        - "correlation(BTC) > 0.7 AND volatility < 0.5"

        Example:
        ```graphql
        query {
          symbolUniverse(query: "market_cap > 100M AND volume_24h > 5M AND (sector = 'defi' OR sector = 'gaming')") {
            symbol
            name
            marketCap
            volume24h
            sector
          }
        }
        ```
        """
        return await SymbolResolver.query_universe(query)


@strawberry.type
class Mutation:
    """Root GraphQL mutation type."""

    @strawberry.mutation
    async def create_custom_strategy(
        self,
        name: str,
        code: str,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Strategy:
        """
        Create a custom strategy.

        Example:
        ```graphql
        mutation {
          createCustomStrategy(
            name: "MyCustomStrategy",
            code: "class MyCustomStrategy(BaseStrategy):...",
            description: "My custom momentum strategy",
            parameters: {"ema_period": 20, "rsi_period": 14}
          ) {
            id
            name
            description
          }
        }
        ```
        """
        return await StrategyResolver.create_strategy(
            name, code, description, parameters
        )

    @strawberry.mutation
    async def update_symbol_metadata(
        self,
        symbol: str,
        tags: Optional[List[str]] = None,
        sector: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> Symbol:
        """
        Update symbol metadata.

        Example:
        ```graphql
        mutation {
          updateSymbolMetadata(
            symbol: "ETH",
            tags: ["smart-contracts", "defi", "layer1"],
            sector: "infrastructure",
            customData: {"ecosystem_tvl": 50000000000}
          ) {
            symbol
            tags
            sector
          }
        }
        ```
        """
        return await SymbolResolver.update_metadata(
            symbol, tags, sector, custom_data
        )


@strawberry.type
class Subscription:
    """Root GraphQL subscription type for real-time updates."""

    @strawberry.subscription
    async def symbol_updates(
        self,
        symbols: List[str]
    ) -> Symbol:
        """
        Subscribe to real-time symbol updates.

        Example:
        ```graphql
        subscription {
          symbolUpdates(symbols: ["BTC", "ETH"]) {
            symbol
            price
            volume24h
            priceChange24h
            timestamp
          }
        }
        ```
        """
        async for symbol in SymbolResolver.subscribe_updates(symbols):
            yield symbol

    @strawberry.subscription
    async def backtest_progress(
        self,
        task_id: str
    ) -> BacktestResult:
        """
        Subscribe to backtest progress updates.

        Example:
        ```graphql
        subscription {
          backtestProgress(taskId: "abc123") {
            progress
            currentSymbol
            completedSymbols
            estimatedTimeRemaining
          }
        }
        ```
        """
        async for update in BacktestResolver.subscribe_progress(task_id):
            yield update


# Create the schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)