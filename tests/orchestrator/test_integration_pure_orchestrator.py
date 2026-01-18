"""
test_integration_pure_orchestrator.py
──────────────────────────────────────────────────────────────────────────
Integration tests for the pure function orchestrator.
These tests verify the full end-to-end flow with Docker container execution.
"""

import asyncio
import pytest
from datetime import datetime

from app.dto.orchestrator.OrchestratorInput import (
    OrchestratorInput,
    StrategyParameters,
)
from app.services.orchestrator.OrchestratorService import OrchestratorService


class TestOrchestratorServiceIntegration:
    """Integration tests for OrchestratorService with pure function approach."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Docker, MongoDB, and full environment setup")
    async def test_full_backtest_with_prefetch(self):
        """
        Test the complete backtest flow:
        1. Create OrchestratorInput configuration
        2. OrchestratorService pre-fetches data from MongoDB
        3. Container spawned WITHOUT database credentials
        4. Container receives pre-fetched data via stdin
        5. Container runs backtest (pure function)
        6. Results returned via stdout
        """
        # Initialize service
        OrchestratorService.initialize(force_rebuild=False)

        # Create configuration
        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(
                name="PeakEMAReversalStrategy",
                params={"ema_window": 15}
            ),
            symbols=["BTCUSDT"],
            interval="1d",
            num_iterations=30,
            initial_capital=100_000,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Run backtest (should pre-fetch data and pass to container)
        run_id, result = await OrchestratorService.run_backtest(
            cfg=orchestrator_input,
            strategy_code="",  # Using built-in strategy
        )

        # Verify results
        assert run_id is not None
        assert isinstance(result, dict)
        assert "symbol_count" in result
        assert result["symbol_count"] == 1
        assert "interval" in result
        assert result["interval"] == "1d"
        assert "strategy" in result

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Docker and MongoDB")
    async def test_container_has_no_network_access(self):
        """
        Verify that the container truly has no network access.
        This test would need to inspect the container configuration.
        """
        OrchestratorService.initialize(force_rebuild=False)

        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(name="PeakEMAReversalStrategy"),
            symbols=["BTCUSDT"],
            interval="1d",
            num_iterations=10,
        )

        # Generate container config
        run_id = OrchestratorService._generate_run_id(orchestrator_input)
        container_config = OrchestratorService._container_config(run_id)

        # Verify no database credentials in environment
        env = container_config.get("environment", {})
        assert "MONGO_USER_PW" not in env
        assert "MONGO_RO_URI" not in env
        assert "MONGO_URI_SLAVE" not in env

        # Verify network mode is "none"
        assert container_config.get("network_mode") == "none"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires MongoDB")
    async def test_data_prefetch_service_caching(self):
        """
        Test that pre-fetched data is properly cached by DataPrefetchService.
        Running the same backtest twice should reuse cached data.
        """
        OrchestratorService.initialize(force_rebuild=False)

        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(name="PeakEMAReversalStrategy"),
            symbols=["BTCUSDT", "ETHUSDT"],
            interval="1d",
            num_iterations=60,
        )

        # Run first backtest
        run_id_1, result_1 = await OrchestratorService.run_backtest(
            cfg=orchestrator_input,
            strategy_code="",
        )

        # Run second backtest with same config (should use cache)
        run_id_2, result_2 = await OrchestratorService.run_backtest(
            cfg=orchestrator_input,
            strategy_code="",
        )

        # Should have same run_id (deterministic based on config)
        assert run_id_1 == run_id_2

        # Results should be identical (from cache)
        assert result_1 == result_2


class TestPureFunctionProperties:
    """Test that the pure function properties hold."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires full environment")
    async def test_determinism(self):
        """
        Test that running the same backtest multiple times produces identical results.
        This is the key property of a pure function.
        """
        OrchestratorService.initialize(force_rebuild=False)

        orchestrator_input = OrchestratorInput(
            strategy=StrategyParameters(name="PeakEMAReversalStrategy"),
            symbols=["BTCUSDT"],
            interval="1d",
            num_iterations=30,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        results = []
        for _ in range(3):
            _, result = await OrchestratorService.run_backtest(
                cfg=orchestrator_input,
                strategy_code="",
            )
            results.append(result)

        # All results should be identical
        for i in range(1, len(results)):
            assert results[0]["symbol_count"] == results[i]["symbol_count"]
            assert results[0]["interval"] == results[i]["interval"]
            assert results[0]["strategy"] == results[i]["strategy"]

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires full environment")
    async def test_no_side_effects(self):
        """
        Test that running a backtest has no side effects on the database.
        The container should only READ (via pre-fetched data) and never WRITE.
        """
        # This test would need to:
        # 1. Take a snapshot of database state before backtest
        # 2. Run backtest
        # 3. Verify database state is unchanged
        # 4. Verify no network calls were made from container
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
