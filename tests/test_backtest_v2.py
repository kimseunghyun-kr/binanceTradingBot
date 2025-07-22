"""
Test Suite for Enhanced Backtest System
──────────────────────────────────────────────────────────────────────────
Comprehensive tests for the new architecture.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.services.BackTestServiceV2 import BackTestServiceV2
from app.services.orchestrator.OrchestratorPoolService import OrchestratorPoolService
from app.dto.orchestrator.OrchestratorInput import OrchestratorInput, StrategyParameters


# Fixtures
@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def async_client():
    """Create async test client."""
    return AsyncClient(app=app, base_url="http://test")


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {"username": "testuser", "user_id": "123"}


@pytest.fixture
def sample_strategy_code():
    """Sample strategy code for testing."""
    return """
from entities.strategies.BaseStrategy import BaseStrategy
import pandas as pd

class TestStrategy(BaseStrategy):
    def __init__(self, ema_period=20):
        super().__init__()
        self.ema_period = ema_period
    
    def generate_signal(self, symbol: str, data: pd.DataFrame, current_candle: pd.Series) -> int:
        if len(data) < self.ema_period:
            return 0
        
        ema = data['close'].ewm(span=self.ema_period).mean()
        
        if current_candle['close'] > ema.iloc[-1]:
            return 1  # Buy
        elif current_candle['close'] < ema.iloc[-1]:
            return -1  # Sell
        
        return 0
    
    def get_parameters(self):
        return {"ema_period": self.ema_period}
"""


@pytest.fixture
def sample_backtest_request():
    """Sample backtest request."""
    return {
        "strategy_name": "TestStrategy",
        "strategy_params": {"ema_period": 20},
        "symbols": ["BTC", "ETH"],
        "interval": "1h",
        "num_iterations": 100,
        "initial_capital": 10000,
        "position_size_pct": 5,
        "tp_ratio": 0.1,
        "sl_ratio": 0.05,
        "stream_progress": True
    }


class TestBacktestServiceV2:
    """Test BackTestServiceV2."""
    
    @pytest.mark.asyncio
    async def test_run_backtest_basic(self, sample_strategy_code):
        """Test basic backtest execution."""
        with patch.object(OrchestratorService, 'run_backtest') as mock_run:
            mock_run.return_value = {
                "status": "success",
                "total_return": 15.5,
                "sharpe_ratio": 1.2,
                "max_drawdown": 5.3,
                "win_rate": 65
            }
            
            result = await BackTestServiceV2.run_backtest(
                strategy_name="TestStrategy",
                strategy_params={"ema_period": 20},
                symbols=["BTC", "ETH"],
                interval="1h",
                num_iterations=100,
                custom_strategy_code=sample_strategy_code
            )
            
            assert result["status"] == "success"
            assert result["total_return"] == 15.5
            assert mock_run.called
    
    @pytest.mark.asyncio
    async def test_run_backtest_with_cache(self):
        """Test backtest with caching."""
        # First run
        with patch.object(OrchestratorService, 'run_backtest') as mock_run:
            mock_run.return_value = {"status": "success", "total_return": 10}
            
            result1 = await BackTestServiceV2.run_backtest(
                strategy_name="TestStrategy",
                strategy_params={"ema_period": 20},
                symbols=["BTC"],
                interval="1h",
                num_iterations=50,
                use_cache=True
            )
            
            assert mock_run.call_count == 1
        
        # Second run (should use cache)
        with patch.object(BackTestServiceV2, '_get_cached_result') as mock_cache:
            mock_cache.return_value = {"status": "success", "total_return": 10}
            
            result2 = await BackTestServiceV2.run_backtest(
                strategy_name="TestStrategy",
                strategy_params={"ema_period": 20},
                symbols=["BTC"],
                interval="1h",
                num_iterations=50,
                use_cache=True
            )
            
            assert result2 == result1
            assert mock_cache.called
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in backtest."""
        with patch.object(OrchestratorService, 'run_backtest') as mock_run:
            mock_run.side_effect = Exception("Orchestrator failed")
            
            with pytest.raises(Exception) as exc_info:
                await BackTestServiceV2.run_backtest(
                    strategy_name="InvalidStrategy",
                    strategy_params={},
                    symbols=["BTC"],
                    interval="1h",
                    num_iterations=100
                )
            
            assert "Orchestrator failed" in str(exc_info.value)


class TestOrchestratorPoolService:
    """Test OrchestratorPoolService."""
    
    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test container pool initialization."""
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client
            
            # Mock container creation
            mock_container = Mock()
            mock_container.id = "test_container_123"
            mock_container.status = "running"
            mock_client.containers.create.return_value = mock_container
            
            await OrchestratorPoolService.initialize()
            
            assert mock_client.containers.create.called
            pool_status = await OrchestratorPoolService.get_pool_status()
            assert pool_status["total_containers"] > 0
    
    @pytest.mark.asyncio
    async def test_run_backtest_streaming(self):
        """Test backtest with progress streaming."""
        mock_container = Mock()
        mock_container.in_use = False
        mock_container.container_obj = Mock()
        
        with patch.object(OrchestratorPoolService, '_get_available_container') as mock_get:
            mock_get.return_value = mock_container
            
            with patch.object(OrchestratorPoolService, '_execute_in_container') as mock_exec:
                mock_exec.return_value = {
                    "status": "success",
                    "total_return": 20
                }
                
                results = []
                async for result in OrchestratorPoolService.run_backtest(
                    strategy_code="test code",
                    strategy_config={"name": "TestStrategy"},
                    symbols=["BTC"],
                    interval="1h",
                    num_iterations=100,
                    stream_progress=True
                ):
                    results.append(result)
                
                assert len(results) > 0
                assert results[-1]["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_container_recycling(self):
        """Test container recycling."""
        mock_container = Mock()
        mock_container.container_id = "test_123"
        mock_container.container_obj = Mock()
        mock_container.run_count = 100  # Over limit
        
        OrchestratorPoolService._container_pool = [mock_container]
        
        await OrchestratorPoolService._recycle_container(mock_container)
        
        assert mock_container.container_obj.stop.called
        assert mock_container.container_obj.remove.called


class TestBacktestControllerV2:
    """Test BacktestControllerV2 endpoints."""
    
    def test_submit_backtest(self, client, mock_user, sample_backtest_request):
        """Test backtest submission endpoint."""
        with patch('app.controller.BacktestControllerV2.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('app.controller.BacktestControllerV2.run_backtest_task.delay') as mock_task:
                mock_result = Mock()
                mock_result.id = "task_123"
                mock_task.return_value = mock_result
                
                response = client.post(
                    "/api/v2/backtest/submit",
                    json=sample_backtest_request
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["task_id"] == "task_123"
                assert data["status"] == "submitted"
                assert "websocket_url" in data
    
    def test_get_backtest_status(self, client, mock_user):
        """Test getting backtest status."""
        with patch('app.controller.BacktestControllerV2.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('app.tasks.celery_app.AsyncResult') as mock_result:
                mock_async_result = Mock()
                mock_async_result.state = "SUCCESS"
                mock_async_result.result = {"total_return": 15}
                mock_result.return_value = mock_async_result
                
                response = client.get("/api/v2/backtest/status/task_123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["state"] == "SUCCESS"
                assert data["progress"] == 100
    
    @pytest.mark.asyncio
    async def test_websocket_streaming(self, async_client):
        """Test WebSocket progress streaming."""
        async with async_client as ac:
            with ac.websocket_connect("/api/v2/backtest/stream/task_123") as websocket:
                # Mock progress updates
                progress_updates = [
                    {"type": "progress", "data": {"progress": 25}},
                    {"type": "progress", "data": {"progress": 50}},
                    {"type": "progress", "data": {"progress": 75}},
                    {"type": "complete", "data": {"total_return": 20}}
                ]
                
                for update in progress_updates:
                    data = await websocket.receive_json()
                    assert data["type"] in ["progress", "complete", "heartbeat"]


class TestGraphQLAPI:
    """Test GraphQL API."""
    
    def test_graphql_symbol_query(self, client):
        """Test GraphQL symbol query."""
        query = """
        query {
            symbols(filter: {marketCapMin: 1000000}) {
                symbol
                name
                marketCap
            }
        }
        """
        
        with patch('app.graphql.resolvers.SymbolResolver.get_symbols') as mock_resolver:
            mock_resolver.return_value = [
                Mock(symbol="BTC", name="Bitcoin", market_cap=1000000000)
            ]
            
            response = client.post(
                "/api/v2/graphql",
                json={"query": query}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]["symbols"]) > 0
    
    def test_graphql_strategy_mutation(self, client, sample_strategy_code):
        """Test GraphQL strategy creation."""
        mutation = """
        mutation {
            createCustomStrategy(
                name: "MyTestStrategy",
                code: "%s",
                description: "Test strategy"
            ) {
                id
                name
            }
        }
        """ % sample_strategy_code.replace('"', '\\"').replace('\n', '\\n')
        
        with patch('app.graphql.resolvers.StrategyResolver.create_strategy') as mock_create:
            mock_create.return_value = Mock(id="123", name="MyTestStrategy")
            
            response = client.post(
                "/api/v2/graphql",
                json={"query": mutation}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["createCustomStrategy"]["name"] == "MyTestStrategy"


class TestSecurity:
    """Test security features."""
    
    def test_rate_limiting(self, client):
        """Test rate limiting."""
        # Make many requests quickly
        responses = []
        for _ in range(15):  # Exceed limit of 10/minute for /backtest
            response = client.post(
                "/api/v2/backtest/submit",
                json={"strategy_name": "test"}
            )
            responses.append(response)
        
        # Should get rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        assert rate_limited
    
    def test_cors_headers(self, client):
        """Test CORS headers."""
        response = client.options("/api/v2/backtest/submit")
        
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_security_headers(self, client):
        """Test security headers."""
        response = client.get("/health")
        
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert "strict-transport-security" in response.headers


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_backtest_flow(self, async_client, sample_strategy_code):
        """Test complete backtest flow from submission to results."""
        # 1. Submit backtest
        submit_response = await async_client.post(
            "/api/v2/backtest/submit",
            json={
                "strategy_name": "TestStrategy",
                "strategy_params": {"ema_period": 20},
                "symbols": ["BTC"],
                "interval": "1h",
                "num_iterations": 50,
                "custom_strategy_code": sample_strategy_code
            }
        )
        
        assert submit_response.status_code == 200
        task_id = submit_response.json()["task_id"]
        
        # 2. Check status
        await asyncio.sleep(2)
        
        status_response = await async_client.get(
            f"/api/v2/backtest/status/{task_id}"
        )
        
        assert status_response.status_code == 200
        assert status_response.json()["task_id"] == task_id
        
        # 3. Get results (when complete)
        # In real test, would wait for completion
        with patch('app.core.mongodb_config.mongodb_config.get_master_client') as mock_mongo:
            mock_db = Mock()
            mock_mongo.return_value = {settings.MONGO_DB: mock_db}
            mock_db.backtest_results.find_one.return_value = {
                "task_id": task_id,
                "total_return": 15,
                "status": "success"
            }
            
            results_response = await async_client.get(
                f"/api/v2/backtest/results/{task_id}"
            )
            
            assert results_response.status_code == 200
            assert results_response.json()["total_return"] == 15


# Performance tests
class TestPerformance:
    """Performance and load tests."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_backtests(self, async_client):
        """Test handling multiple concurrent backtests."""
        tasks = []
        
        for i in range(10):
            task = async_client.post(
                "/api/v2/backtest/submit",
                json={
                    "strategy_name": f"TestStrategy{i}",
                    "symbols": ["BTC", "ETH"],
                    "interval": "1h",
                    "num_iterations": 100
                }
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
        assert successful >= 8  # At least 80% should succeed
    
    @pytest.mark.benchmark
    def test_strategy_execution_speed(self, benchmark):
        """Benchmark strategy execution speed."""
        import pandas as pd
        import numpy as np
        
        # Create sample data
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='1h')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.randn(1000).cumsum() + 100,
            'high': np.random.randn(1000).cumsum() + 101,
            'low': np.random.randn(1000).cumsum() + 99,
            'close': np.random.randn(1000).cumsum() + 100,
            'volume': np.random.randint(1000, 10000, 1000)
        })
        data.set_index('timestamp', inplace=True)
        
        def run_strategy():
            # Simulate strategy execution
            ema = data['close'].ewm(span=20).mean()
            signals = (data['close'] > ema).astype(int)
            return signals.sum()
        
        result = benchmark(run_strategy)
        assert result > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])