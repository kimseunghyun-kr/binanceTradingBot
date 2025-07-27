"""
GraphQL Resolvers
──────────────────────────────────────────────────────────────────────────
Resolver implementations for GraphQL queries, mutations, and subscriptions.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator

from app.core.init_services import get_data_service, slave_db_app_sync, master_db_app_async
from app.core.pydanticConfig.settings import get_settings

settings = get_settings()
from app.graphql.types import (
    Symbol, SymbolFilter, SymbolStats,
    Strategy, StrategyFilter, StrategyPerformance,
    BacktestResult, BacktestFilter, Trade,
    MarketMetrics
)



class SymbolResolver:
    """Resolver for symbol-related queries."""

    @staticmethod
    async def get_symbols(
            filter: Optional[SymbolFilter] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List[Symbol]:
        """Get symbols with flexible filtering."""
        # Use read-only database for queries
        db = await slave_db_app_sync()

        # Build MongoDB query
        query = {}

        if filter:
            if filter.symbols:
                query["symbol"] = {"$in": filter.symbols}

            if filter.market_cap_min or filter.market_cap_max:
                query["market_cap"] = {}
                if filter.market_cap_min:
                    query["market_cap"]["$gte"] = filter.market_cap_min
                if filter.market_cap_max:
                    query["market_cap"]["$lte"] = filter.market_cap_max

            if filter.volume_min or filter.volume_max:
                query["volume_24h"] = {}
                if filter.volume_min:
                    query["volume_24h"]["$gte"] = filter.volume_min
                if filter.volume_max:
                    query["volume_24h"]["$lte"] = filter.volume_max

            if filter.tags:
                query["tags"] = {"$in": filter.tags}

            if filter.sectors:
                query["sector"] = {"$in": filter.sectors}

            if filter.exchanges:
                query["exchanges"] = {"$in": filter.exchanges}

        # Execute query
        cursor = db.symbols.find(query).skip(offset).limit(limit)

        symbols = []
        async for doc in cursor:
            symbols.append(Symbol(
                symbol=doc["symbol"],
                name=doc.get("name", ""),
                market_cap=doc.get("market_cap", 0),
                volume_24h=doc.get("volume_24h", 0),
                price=doc.get("price", 0),
                price_change_24h=doc.get("price_change_24h", 0),
                price_change_7d=doc.get("price_change_7d"),
                circulating_supply=doc.get("circulating_supply"),
                total_supply=doc.get("total_supply"),
                tags=doc.get("tags", []),
                sector=doc.get("sector"),
                exchanges=doc.get("exchanges", []),
                last_updated=doc.get("last_updated", datetime.utcnow())
            ))

        return symbols

    @staticmethod
    async def get_symbol_stats(
            symbols: List[str],
            timeframe: str = "24h"
    ) -> List[SymbolStats]:
        """Get detailed statistics for symbols."""
        stats = []

        # Convert timeframe to interval
        timeframe_map = {
            "1h": "1h",
            "24h": "1d",
            "7d": "1w",
            "30d": "1M"
        }
        interval = timeframe_map.get(timeframe, "1d")

        for symbol in symbols:
            # Fetch candle data
            data_service = get_data_service()
            df = await data_service.get_candles(
                symbol=symbol,
                interval=interval,
                limit=100
            )

            if df is not None and not df.empty:
                # Calculate statistics
                high = df['high'].max()
                low = df['low'].min()
                open_price = df.iloc[0]['open']
                close_price = df.iloc[-1]['close']
                volume = df['volume'].sum()
                trades = len(df)

                # Calculate volatility (standard deviation of returns)
                returns = df['close'].pct_change().dropna()
                volatility = returns.std() * (365 ** 0.5)  # Annualized

                stats.append(SymbolStats(
                    symbol=symbol,
                    timeframe=timeframe,
                    high=high,
                    low=low,
                    open=open_price,
                    close=close_price,
                    volume=volume,
                    trades=trades,
                    volatility=volatility
                ))

        return stats

    @staticmethod
    async def query_universe(query: str) -> List[Symbol]:
        """
        Execute advanced query language for symbol selection.

        Example queries:
        - "market_cap > 1B AND volume_24h > 10M"
        - "rsi_14 < 30 OR rsi_14 > 70"
        """
        # Parse query into MongoDB filter
        # This is a simplified implementation - in production, use a proper parser
        mongo_query = SymbolResolver._parse_query_to_mongo(query)

        # Use read-only database for queries
        db = await slave_db_app_sync()

        cursor = db.symbols.find(mongo_query).limit(1000)

        symbols = []
        async for doc in cursor:
            symbols.append(Symbol(
                symbol=doc["symbol"],
                name=doc.get("name", ""),
                market_cap=doc.get("market_cap", 0),
                volume_24h=doc.get("volume_24h", 0),
                price=doc.get("price", 0),
                price_change_24h=doc.get("price_change_24h", 0),
                tags=doc.get("tags", []),
                sector=doc.get("sector"),
                exchanges=doc.get("exchanges", [])
            ))

        return symbols

    @staticmethod
    def _parse_query_to_mongo(query: str) -> Dict[str, Any]:
        """Parse query string to MongoDB query."""
        # Simplified parser - in production, use a proper query parser
        mongo_query = {}

        # Handle basic comparisons
        if "market_cap >" in query:
            value = float(query.split("market_cap >")[1].split()[0].replace("B", "e9").replace("M", "e6"))
            mongo_query["market_cap"] = {"$gt": value}

        if "volume_24h >" in query:
            value = float(query.split("volume_24h >")[1].split()[0].replace("B", "e9").replace("M", "e6"))
            mongo_query["volume_24h"] = {"$gt": value}

        return mongo_query

    @staticmethod
    async def update_metadata(
            symbol: str,
            tags: Optional[List[str]] = None,
            sector: Optional[str] = None,
            custom_data: Optional[Dict[str, Any]] = None
    ) -> Symbol:
        """Update symbol metadata."""
        # Use master database for writes
        db = master_db_app_async()

        update_doc = {}
        if tags is not None:
            update_doc["tags"] = tags
        if sector is not None:
            update_doc["sector"] = sector
        if custom_data:
            update_doc.update(custom_data)

        update_doc["last_updated"] = datetime.utcnow()

        result = await db.symbols.find_one_and_update(
            {"symbol": symbol},
            {"$set": update_doc},
            return_document=True
        )

        if not result:
            raise ValueError(f"Symbol {symbol} not found")

        return Symbol(
            symbol=result["symbol"],
            name=result.get("name", ""),
            market_cap=result.get("market_cap", 0),
            volume_24h=result.get("volume_24h", 0),
            price=result.get("price", 0),
            price_change_24h=result.get("price_change_24h", 0),
            tags=result.get("tags", []),
            sector=result.get("sector")
        )

    @staticmethod
    async def subscribe_updates(symbols: List[str]) -> AsyncGenerator[Symbol, None]:
        """Subscribe to real-time symbol updates."""
        # In production, this would connect to a WebSocket feed
        # For now, simulate with periodic updates
        while True:
            for symbol in symbols:
                # Fetch latest data
                mongo_client = slave_db_app_sync()
                db = mongo_client[settings.MONGO_DB]

                doc = await db.symbols.find_one({"symbol": symbol})
                if doc:
                    yield Symbol(
                        symbol=doc["symbol"],
                        name=doc.get("name", ""),
                        market_cap=doc.get("market_cap", 0),
                        volume_24h=doc.get("volume_24h", 0),
                        price=doc.get("price", 0),
                        price_change_24h=doc.get("price_change_24h", 0),
                        timestamp=datetime.utcnow()
                    )

            await asyncio.sleep(5)  # Update every 5 seconds


class StrategyResolver:
    """Resolver for strategy-related queries."""

    @staticmethod
    async def get_strategies(
            filter: Optional[StrategyFilter] = None
    ) -> List[Strategy]:
        """Get available strategies."""
        # Use read-only database for queries
        db = await slave_db_app_sync()

        query = {}

        if filter:
            if filter.name_contains:
                query["name"] = {"$regex": filter.name_contains, "$options": "i"}
            if filter.type:
                query["type"] = filter.type.value
            if filter.is_active is not None:
                query["is_active"] = filter.is_active
            if filter.created_after:
                query["created_at"] = {"$gte": filter.created_after}

        cursor = db.strategies.find(query)

        strategies = []
        async for doc in cursor:
            # Calculate performance if available
            performance = None
            if "backtest_results" in doc:
                performance = StrategyResolver._calculate_performance(
                    doc["backtest_results"]
                )

            strategies.append(Strategy(
                id=str(doc["_id"]),
                name=doc["name"],
                description=doc.get("description"),
                type=doc.get("type", "custom"),
                parameters=doc.get("parameters", {}),
                required_indicators=doc.get("required_indicators", []),
                performance=performance,
                created_at=doc.get("created_at", datetime.utcnow()),
                updated_at=doc.get("updated_at", datetime.utcnow()),
                is_active=doc.get("is_active", True),
                version=doc.get("version", "1.0.0")
            ))

        return strategies

    @staticmethod
    def _calculate_performance(results: List[Dict]) -> StrategyPerformance:
        """Calculate strategy performance from backtest results."""
        if not results:
            return None

        total_trades = sum(r.get("total_trades", 0) for r in results)
        winning_trades = sum(r.get("winning_trades", 0) for r in results)
        losing_trades = sum(r.get("losing_trades", 0) for r in results)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Aggregate other metrics
        avg_sharpe = sum(r.get("sharpe_ratio", 0) for r in results) / len(results)
        max_dd = max(r.get("max_drawdown", 0) for r in results)

        return StrategyPerformance(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            average_win=0,  # TODO: Calculate from trade data
            average_loss=0,
            profit_factor=0,
            sharpe_ratio=avg_sharpe,
            max_drawdown=max_dd
        )

    @staticmethod
    async def create_strategy(
            name: str,
            code: str,
            description: Optional[str] = None,
            parameters: Optional[Dict[str, Any]] = None
    ) -> Strategy:
        """Create a new custom strategy."""
        # Use master database for writes
        db = master_db_app_async()

        # Validate strategy code (basic validation)
        if "class" not in code or "BaseStrategy" not in code:
            raise ValueError("Invalid strategy code")

        strategy_doc = {
            "name": name,
            "code": code,
            "description": description,
            "type": "custom",
            "parameters": parameters or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "version": "1.0.0"
        }

        result = await db.strategies.insert_one(strategy_doc)
        strategy_doc["_id"] = result.inserted_id

        return Strategy(
            id=str(result.inserted_id),
            name=name,
            description=description,
            type="custom",
            parameters=parameters or {},
            created_at=strategy_doc["created_at"],
            updated_at=strategy_doc["updated_at"],
            is_active=True,
            version="1.0.0"
        )


class BacktestResolver:
    """Resolver for backtest-related queries."""

    @staticmethod
    async def get_results(
            filter: Optional[BacktestFilter] = None,
            limit: int = 50,
            offset: int = 0
    ) -> List[BacktestResult]:
        """Get backtest results."""
        # Use read-only database for queries
        db = await slave_db_app_sync()

        query = {}

        if filter:
            if filter.strategy_name:
                query["metadata.strategy_name"] = filter.strategy_name
            if filter.symbols:
                query["metadata.symbols"] = {"$in": filter.symbols}
            if filter.min_return:
                query["total_return"] = {"$gte": filter.min_return}
            if filter.max_drawdown:
                query["max_drawdown"] = {"$lte": filter.max_drawdown}
            if filter.date_from or filter.date_to:
                query["created_at"] = {}
                if filter.date_from:
                    query["created_at"]["$gte"] = filter.date_from
                if filter.date_to:
                    query["created_at"]["$lte"] = filter.date_to

        cursor = db.backtest_results.find(query).skip(offset).limit(limit)

        results = []
        async for doc in cursor:
            # Convert trades
            trades = []
            for trade_doc in doc.get("trades", []):
                trades.append(Trade(
                    id=trade_doc.get("id", ""),
                    symbol=trade_doc.get("symbol", ""),
                    side=trade_doc.get("side", ""),
                    entry_price=trade_doc.get("entry_price", 0),
                    exit_price=trade_doc.get("exit_price"),
                    quantity=trade_doc.get("quantity", 0),
                    entry_time=trade_doc.get("entry_time", datetime.utcnow()),
                    exit_time=trade_doc.get("exit_time"),
                    pnl=trade_doc.get("pnl"),
                    pnl_percentage=trade_doc.get("pnl_percentage"),
                    fees=trade_doc.get("fees", 0),
                    slippage=trade_doc.get("slippage", 0),
                    status=trade_doc.get("status", "closed")
                ))

            results.append(BacktestResult(
                id=str(doc["_id"]),
                strategy_name=doc.get("metadata", {}).get("strategy_name", ""),
                symbols=doc.get("metadata", {}).get("symbols", []),
                timeframe=doc.get("metadata", {}).get("interval", "1h"),
                start_date=doc.get("start_date", datetime.utcnow()),
                end_date=doc.get("end_date", datetime.utcnow()),
                initial_capital=doc.get("initial_capital", 10000),
                final_capital=doc.get("final_capital", 10000),
                total_return=doc.get("total_return", 0),
                sharpe_ratio=doc.get("sharpe_ratio", 0),
                max_drawdown=doc.get("max_drawdown", 0),
                trades=trades,
                created_at=doc.get("created_at", datetime.utcnow()),
                execution_time_seconds=doc.get("duration_seconds", 0)
            ))

        return results

    @staticmethod
    async def subscribe_progress(task_id: str) -> AsyncGenerator[BacktestResult, None]:
        """Subscribe to backtest progress updates."""
        # In production, this would connect to Celery task events
        # For now, simulate progress updates
        progress = 0
        symbols = ["BTC", "ETH", "BNB", "SOL", "ADA"]
        completed = []

        while progress < 100:
            progress += 10
            current_symbol = symbols[len(completed)] if len(completed) < len(symbols) else None

            if current_symbol and progress % 20 == 0:
                completed.append(current_symbol)

            yield BacktestResult(
                id=task_id,
                progress=progress,
                current_symbol=current_symbol,
                completed_symbols=completed,
                estimated_time_remaining=int((100 - progress) * 2)  # 2 seconds per percent
            )

            await asyncio.sleep(2)


class MarketResolver:
    """Resolver for market-related queries."""

    @staticmethod
    async def get_market_metrics(
            category: Optional[str] = None
    ) -> MarketMetrics:
        """Get overall market metrics."""
        # Use read-only database for queries
        db = await slave_db_app_sync()

        # Aggregate market data
        pipeline = []

        if category:
            pipeline.append({"$match": {"sector": category}})

        pipeline.extend([
            {
                "$group": {
                    "_id": None,
                    "total_market_cap": {"$sum": "$market_cap"},
                    "total_volume_24h": {"$sum": "$volume_24h"},
                    "active_coins": {"$sum": 1}
                }
            }
        ])

        result = await db.symbols.aggregate(pipeline).to_list(1)

        if not result:
            return MarketMetrics(
                total_market_cap=0,
                total_volume_24h=0,
                btc_dominance=0,
                eth_dominance=0,
                active_coins=0,
                timestamp=datetime.utcnow()
            )

        metrics_data = result[0]

        # Calculate dominance
        btc_doc = await db.symbols.find_one({"symbol": "BTC"})
        eth_doc = await db.symbols.find_one({"symbol": "ETH"})

        btc_dominance = 0
        eth_dominance = 0

        if btc_doc and metrics_data["total_market_cap"] > 0:
            btc_dominance = btc_doc["market_cap"] / metrics_data["total_market_cap"] * 100

        if eth_doc and metrics_data["total_market_cap"] > 0:
            eth_dominance = eth_doc["market_cap"] / metrics_data["total_market_cap"] * 100

        return MarketMetrics(
            total_market_cap=metrics_data["total_market_cap"],
            total_volume_24h=metrics_data["total_volume_24h"],
            btc_dominance=btc_dominance,
            eth_dominance=eth_dominance,
            active_coins=metrics_data["active_coins"],
            timestamp=datetime.utcnow()
        )