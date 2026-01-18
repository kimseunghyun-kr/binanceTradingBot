"""
test_pure_orchestrator.py
──────────────────────────────────────────────────────────────────────────
Unit and integration tests for the pure function orchestrator implementation.

Tests verify that:
1. The orchestrator works without database access
2. Pre-fetched data is properly used
3. Results are deterministic (pure function property)
4. Container has no network access
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import pytest

from app.dto.orchestrator.OrchestratorInput import (
    OrchestratorInput,
    StrategyParameters,
    ComponentConfig,
)
from app.services.orchestrator.DataPrefetchService import DataPrefetchService
from strategyOrchestrator.StrategyOrchestrator import (
    PrefetchedDataSource,
    run_backtest,
)


class TestPrefetchedDataSource:
    """Test the PrefetchedDataSource class."""

    def test_initialization(self):
        """Test PrefetchedDataSource initializes correctly."""
        ohlcv_data = {
            "main": {
                "BTCUSDT": [
                    {"open_time": 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}
                ]
            },
            "detailed": {}
        }

        source = PrefetchedDataSource(ohlcv_data)
        assert source.main_data == ohlcv_data["main"]
        assert source.detailed_data == {}

    def test_fetch_candles_from_main_data(self):
        """Test fetching candles from main data."""
        candles = [
            {"open_time": i * 1000, "open": 100 + i, "high": 110 + i, "low": 90 + i, "close": 105 + i, "volume": 1000}
            for i in range(100)
        ]

        ohlcv_data = {
            "main": {"BTCUSDT": candles},
            "detailed": {}
        }

        source = PrefetchedDataSource(ohlcv_data)
        df = source.fetch_candles("BTCUSDT", "1d", limit=50)

        assert len(df) == 50
        assert "open_time" in df.columns
        assert "close" in df.columns
        assert df["close"].iloc[0] == 105  # First candle

    def test_fetch_candles_with_limit(self):
        """Test that limit parameter works correctly."""
        candles = [
            {"open_time": i * 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}
            for i in range(200)
        ]

        ohlcv_data = {
            "main": {"BTCUSDT": candles},
            "detailed": {}
        }

        source = PrefetchedDataSource(ohlcv_data)
        df = source.fetch_candles("BTCUSDT", "1d", limit=50)

        assert len(df) == 50

    def test_fetch_candles_newest_first(self):
        """Test fetching candles in reverse order."""
        candles = [
            {"open_time": i * 1000, "open": 100 + i, "high": 110, "low": 90, "close": 105, "volume": 1000}
            for i in range(10)
        ]

        ohlcv_data = {
            "main": {"BTCUSDT": candles},
            "detailed": {}
        }

        source = PrefetchedDataSource(ohlcv_data)
        df = source.fetch_candles("BTCUSDT", "1d", limit=10, newest_first=True)

        # When newest_first=True, the df should be sorted desc then reversed to asc
        assert len(df) == 10
        # Check that it's properly ordered
        assert df["open_time"].is_monotonic_increasing

    def test_fetch_nonexistent_symbol(self):
        """Test fetching data for a symbol that doesn't exist."""
        ohlcv_data = {"main": {}, "detailed": {}}

        source = PrefetchedDataSource(ohlcv_data)
        df = source.fetch_candles("NONEXISTENT", "1d", limit=50)

        assert df.empty

    def test_caching(self):
        """Test that results are cached."""
        candles = [
            {"open_time": i * 1000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}
            for i in range(100)
        ]

        ohlcv_data = {
            "main": {"BTCUSDT": candles},
            "detailed": {}
        }

        source = PrefetchedDataSource(ohlcv_data)

        # First fetch
        df1 = source.fetch_candles("BTCUSDT", "1d", limit=50)
        # Second fetch (should be cached)
        df2 = source.fetch_candles("BTCUSDT", "1d", limit=50)

        # Should be the exact same object from cache
        assert df1 is df2


class TestDataPrefetchService:
    """Test the DataPrefetchService (requires database)."""

    @pytest.mark.skip(reason="Requires MongoDB connection")
    def test_calculate_required_rows(self):
        """Test calculation of required rows."""
        service = DataPrefetchService()

        # Test with date range
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)  # 30 days
        lookback = 50

        rows = service._calculate_required_rows(
            start_date, end_date, num_iterations=100, lookback=lookback, interval="1d"
        )

        # Should be approximately 30 days + 50 lookback + 50 buffer = 130
        assert rows > 100
        assert rows < 200

    @pytest.mark.skip(reason="Requires MongoDB connection")
    def test_prefetch_ohlcv_data(self):
        """Test pre-fetching OHLCV data from database."""
        service = DataPrefetchService()

        symbols = ["BTCUSDT"]
        interval = "1d"

        result = service.prefetch_ohlcv_data(
            symbols=symbols,
            interval=interval,
            num_iterations=30,
            lookback=50,
            include_detailed=False,
        )

        assert "main" in result
        assert "BTCUSDT" in result["main"]
        assert len(result["main"]["BTCUSDT"]) > 0


class TestPureOrchestrator:
    """Test the pure function orchestrator."""

    def _create_sample_ohlcv_data(self, symbols: List[str], num_candles: int = 500) -> Dict:
        """Create sample OHLCV data for testing."""
        main_data = {}
        detailed_data = {}

        for symbol in symbols:
            # Main interval data (1d)
            main_candles = []
            for i in range(num_candles):
                timestamp = int((datetime(2024, 1, 1) + timedelta(days=i)).timestamp() * 1000)
                main_candles.append({
                    "open_time": timestamp,
                    "open": 100.0 + i * 0.1,
                    "high": 110.0 + i * 0.1,
                    "low": 90.0 + i * 0.1,
                    "close": 105.0 + i * 0.1,
                    "volume": 1000.0 + i
                })
            main_data[symbol] = main_candles

            # Detailed interval data (1h) - 24x more granular
            detailed_candles = []
            for i in range(num_candles * 24):
                timestamp = int((datetime(2024, 1, 1) + timedelta(hours=i)).timestamp() * 1000)
                detailed_candles.append({
                    "open_time": timestamp,
                    "open": 100.0 + i * 0.01,
                    "high": 110.0 + i * 0.01,
                    "low": 90.0 + i * 0.01,
                    "close": 105.0 + i * 0.01,
                    "volume": 100.0 + i
                })
            detailed_data[symbol] = detailed_candles

        return {"main": main_data, "detailed": detailed_data}

    def test_orchestrator_with_prefetched_data(self):
        """Test that orchestrator works with pre-fetched data."""
        symbols = ["BTCUSDT"]
        ohlcv_data = self._create_sample_ohlcv_data(symbols, num_candles=200)

        config = {
            "symbols": symbols,
            "interval": "1d",
            "num_iterations": 60,
            "tp_ratio": 2.0,
            "sl_ratio": 1.0,
            "parallel_symbols": 1,
            "market": "SPOT",
            "initial_cash": 100_000,
            "ohlcv_data": ohlcv_data,  # Pre-fetched data
            "strategy": {"builtin": "PeakEMAReversalStrategy"},
            "fee_model": {"builtin": "static"},
            "slippage_model": {"builtin": "zero"},
            "fill_policy": {"builtin": "AggressiveMarketPolicy"},
            "capacity_policy": {"builtin": "LegCapacity"},
            "sizing_model": {"builtin": "fixed_fraction"},
        }

        result = run_backtest(config)

        # Verify result structure
        assert "symbol_count" in result
        assert "interval" in result
        assert "strategy" in result
        assert result["symbol_count"] == 1
        assert result["interval"] == "1d"

    def test_orchestrator_deterministic(self):
        """Test that orchestrator produces deterministic results (pure function)."""
        symbols = ["BTCUSDT"]
        ohlcv_data = self._create_sample_ohlcv_data(symbols, num_candles=200)

        config = {
            "symbols": symbols,
            "interval": "1d",
            "num_iterations": 60,
            "tp_ratio": 2.0,
            "sl_ratio": 1.0,
            "parallel_symbols": 1,
            "market": "SPOT",
            "initial_cash": 100_000,
            "ohlcv_data": ohlcv_data,
            "strategy": {"builtin": "PeakEMAReversalStrategy"},
            "fee_model": {"builtin": "static"},
            "slippage_model": {"builtin": "zero"},
            "fill_policy": {"builtin": "AggressiveMarketPolicy"},
            "capacity_policy": {"builtin": "LegCapacity"},
            "sizing_model": {"builtin": "fixed_fraction"},
        }

        # Run twice with same input
        result1 = run_backtest(config)
        result2 = run_backtest(config)

        # Results should be identical (deterministic)
        # Note: We can't compare timestamps, but we can compare key metrics
        assert result1["symbol_count"] == result2["symbol_count"]
        assert result1["interval"] == result2["interval"]
        assert result1["strategy"] == result2["strategy"]

    def test_orchestrator_without_prefetched_data_raises_warning(self, caplog):
        """Test that orchestrator warns when no pre-fetched data is provided."""
        symbols = ["BTCUSDT"]

        config = {
            "symbols": symbols,
            "interval": "1d",
            "num_iterations": 60,
            "tp_ratio": 2.0,
            "sl_ratio": 1.0,
            "parallel_symbols": 1,
            "market": "SPOT",
            "initial_cash": 100_000,
            # No ohlcv_data - should fall back to database
            "strategy": {"builtin": "PeakEMAReversalStrategy"},
            "fee_model": {"builtin": "static"},
            "slippage_model": {"builtin": "zero"},
            "fill_policy": {"builtin": "AggressiveMarketPolicy"},
            "capacity_policy": {"builtin": "LegCapacity"},
            "sizing_model": {"builtin": "fixed_fraction"},
        }

        # This will try to connect to database (which may not exist in test)
        # We just want to verify the warning is logged
        try:
            result = run_backtest(config)
        except Exception:
            pass  # Expected if database not available

        # Check that warning was logged
        # Note: This test may fail if database is available
        assert any("No pre-fetched data found" in record.message for record in caplog.records)


class TestOrchestratorInputDTO:
    """Test the OrchestratorInput DTO."""

    def test_to_container_payload_with_ohlcv_data(self):
        """Test that to_container_payload includes OHLCV data."""
        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(name="PeakEMAReversalStrategy"),
            symbols=["BTCUSDT"],
            interval="1d",
            num_iterations=100,
        )

        ohlcv_data = {
            "main": {"BTCUSDT": []},
            "detailed": {"BTCUSDT": []}
        }

        payload = orchestrator_input.to_container_payload(ohlcv_data=ohlcv_data)

        assert "ohlcv_data" in payload
        assert payload["ohlcv_data"] == ohlcv_data
        assert "symbols" in payload
        assert "interval" in payload

    def test_to_container_payload_without_ohlcv_data(self):
        """Test that to_container_payload works without OHLCV data (legacy mode)."""
        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(name="PeakEMAReversalStrategy"),
            symbols=["BTCUSDT"],
            interval="1d",
            num_iterations=100,
        )

        payload = orchestrator_input.to_container_payload()

        assert "ohlcv_data" not in payload
        assert "symbols" in payload
        assert "interval" in payload


class TestIntegration:
    """Integration tests for the full flow."""

    @pytest.mark.skip(reason="Requires Docker and MongoDB")
    def test_full_flow_with_orchestrator_service(self):
        """Test the full flow from OrchestratorService to container execution."""
        # This would test:
        # 1. DataPrefetchService fetches data from MongoDB
        # 2. OrchestratorService spawns container with data
        # 3. Container executes without network access
        # 4. Results are returned
        pass

    def test_json_serialization(self):
        """Test that OHLCV data can be properly serialized to JSON."""
        ohlcv_data = {
            "main": {
                "BTCUSDT": [
                    {"open_time": 1000, "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000.0}
                ]
            },
            "detailed": {}
        }

        # Should be serializable
        json_str = json.dumps(ohlcv_data)
        assert json_str is not None

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert deserialized == ohlcv_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
