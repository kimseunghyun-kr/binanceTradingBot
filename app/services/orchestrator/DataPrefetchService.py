"""
DataPrefetchService.py
──────────────────────────────────────────────────────────────────────────
Service to pre-fetch all required OHLCV data before passing to orchestrator.
This eliminates database access from the Docker container, making it a pure function.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from strategyOrchestrator.repository.candleRepository import CandleRepository

logger = logging.getLogger(__name__)


class DataPrefetchService:
    """
    Pre-fetches all OHLCV data needed for a backtest run.

    This service runs on the HOST side and fetches data from MongoDB,
    then passes it to the container as part of the input payload.
    """

    def __init__(self, mongo_uri: Optional[str] = None, db_name: Optional[str] = None):
        """Initialize with optional MongoDB connection parameters."""
        self.repo = CandleRepository(mongo_uri=mongo_uri, db_name=db_name)

    @staticmethod
    def _calculate_required_rows(
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        num_iterations: int,
        lookback: int,
        interval: str,
    ) -> int:
        """
        Calculate how many candles we need to fetch.

        Args:
            start_date: Start date for backtest (optional)
            end_date: End date for backtest (optional)
            num_iterations: Number of iterations to run
            lookback: Strategy lookback period
            interval: Candle interval (1h, 1d, etc.)

        Returns:
            Number of rows to fetch
        """
        if start_date and end_date:
            # Calculate based on date range
            delta = end_date - start_date

            # Convert interval to timedelta
            interval_hours = {
                "1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 30/60,
                "1h": 1, "2h": 2, "4h": 4, "6h": 6, "12h": 12,
                "1d": 24, "3d": 72, "1w": 168, "1M": 720  # approximate
            }.get(interval, 1)

            rows_for_period = int(delta.total_seconds() / (interval_hours * 3600))
        else:
            # Use num_iterations
            rows_for_period = num_iterations

        # Add buffer for lookback and safety margin
        total_rows = rows_for_period + lookback + 50
        logger.info(f"Calculated required rows: {total_rows} (period: {rows_for_period}, lookback: {lookback})")
        return total_rows

    def prefetch_ohlcv_data(
        self,
        symbols: List[str],
        interval: str,
        num_iterations: int = 100,
        lookback: int = 200,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_detailed: bool = True,
    ) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Pre-fetch all OHLCV data for the given symbols and parameters.

        Args:
            symbols: List of trading symbols (e.g., ["BTCUSDT", "ETHUSDT"])
            interval: Main candle interval (e.g., "1d", "1h")
            num_iterations: Number of iterations to backtest
            lookback: Strategy lookback period
            start_date: Optional start date for backtest
            end_date: Optional end date for backtest
            include_detailed: Whether to include detailed candles for execution

        Returns:
            Dictionary structure:
            {
                "main": {
                    "BTCUSDT": [{"open_time": ..., "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}, ...],
                    "ETHUSDT": [...],
                },
                "detailed": {  # Only if include_detailed=True
                    "BTCUSDT": [...],
                    "ETHUSDT": [...],
                }
            }
        """
        logger.info(f"Pre-fetching OHLCV data for {len(symbols)} symbols at {interval} interval")

        # Calculate how many rows we need
        required_rows = self._calculate_required_rows(
            start_date, end_date, num_iterations, lookback, interval
        )

        # Fetch main interval data for all symbols
        main_data = {}
        for symbol in symbols:
            try:
                df = self.repo.fetch_candles(
                    symbol=symbol,
                    interval=interval,
                    limit=required_rows,
                    newest_first=False,  # Oldest to newest
                )

                if df.empty:
                    logger.warning(f"No data fetched for {symbol} at {interval}")
                    main_data[symbol] = []
                else:
                    # Convert to list of dicts for JSON serialization
                    main_data[symbol] = df.to_dict(orient='records')
                    logger.info(f"Fetched {len(df)} candles for {symbol} at {interval}")

            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                main_data[symbol] = []

        result = {"main": main_data}

        # Fetch detailed interval data if requested (for timeline execution)
        if include_detailed:
            detail_interval = "1h" if interval in {"1d", "1w"} else "15m"
            detailed_data = {}

            # For detailed data, we need more rows (higher resolution)
            detail_multiplier = {
                "1d": 24,   # 24x 1h candles per day
                "1w": 168,  # 168x 1h candles per week
                "4h": 16,   # 16x 15m candles per 4h
                "1h": 4,    # 4x 15m candles per 1h
            }.get(interval, 10)

            detail_rows = required_rows * detail_multiplier
            detail_rows = min(detail_rows, 10_000)  # Cap at 10k candles

            for symbol in symbols:
                try:
                    df = self.repo.fetch_candles(
                        symbol=symbol,
                        interval=detail_interval,
                        limit=detail_rows,
                        newest_first=False,
                    )

                    if df.empty:
                        logger.warning(f"No detailed data fetched for {symbol} at {detail_interval}")
                        detailed_data[symbol] = []
                    else:
                        detailed_data[symbol] = df.to_dict(orient='records')
                        logger.info(f"Fetched {len(df)} detailed candles for {symbol} at {detail_interval}")

                except Exception as e:
                    logger.error(f"Error fetching detailed data for {symbol}: {e}")
                    detailed_data[symbol] = []

            result["detailed"] = detailed_data

        total_candles = sum(len(data) for data in main_data.values())
        if include_detailed:
            total_candles += sum(len(data) for data in result.get("detailed", {}).values())

        logger.info(f"Pre-fetch complete: {total_candles} total candles for {len(symbols)} symbols")
        return result

    def prefetch_with_strategy_lookback(
        self,
        symbols: List[str],
        interval: str,
        strategy_lookback: int,
        num_iterations: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Convenience method that uses strategy's required lookback.

        Args:
            symbols: List of trading symbols
            interval: Candle interval
            strategy_lookback: Lookback period from strategy.get_required_lookback()
            num_iterations: Number of iterations
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Pre-fetched OHLCV data dictionary
        """
        return self.prefetch_ohlcv_data(
            symbols=symbols,
            interval=interval,
            num_iterations=num_iterations,
            lookback=strategy_lookback,
            start_date=start_date,
            end_date=end_date,
            include_detailed=True,
        )
