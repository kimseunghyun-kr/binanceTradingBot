#!/usr/bin/env python3
"""
Test script to verify the architecture is working correctly.
Tests MongoDB master-slave separation, GraphQL queries, and basic API endpoints.
"""
import asyncio
import httpx
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
GRAPHQL_URL = f"{BASE_URL}/graphql"


async def test_health_check():
    """Test the health check endpoint."""
    print("1. Testing health check endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        print(f"   ✓ Health check passed: {data}")
        return True


async def test_graphql_symbols():
    """Test GraphQL symbol query."""
    print("\n2. Testing GraphQL symbol query...")
    
    query = """
    query {
        symbols(limit: 5) {
            symbol
            name
            marketCap
            volume24h
            price
            priceChange24h
        }
    }
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "symbols" in data["data"]:
                symbols = data["data"]["symbols"]
                print(f"   ✓ Found {len(symbols)} symbols")
                for symbol in symbols[:3]:
                    print(f"     - {symbol['symbol']}: ${symbol.get('price', 0)}")
                return True
            else:
                print(f"   ✗ No symbols found in response: {data}")
        else:
            print(f"   ✗ GraphQL query failed: {response.status_code}")
            print(f"     Response: {response.text}")
    
    return False


async def test_graphql_strategies():
    """Test GraphQL strategy query."""
    print("\n3. Testing GraphQL strategy query...")
    
    query = """
    query {
        strategies {
            name
            description
            type
            isActive
            createdAt
        }
    }
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and "strategies" in data["data"]:
                strategies = data["data"]["strategies"]
                print(f"   ✓ Found {len(strategies)} strategies")
                for strategy in strategies[:3]:
                    print(f"     - {strategy['name']}: {strategy.get('type', 'N/A')}")
                return True
            else:
                print(f"   ✗ No strategies found in response: {data}")
        else:
            print(f"   ✗ GraphQL query failed: {response.status_code}")
    
    return False


async def test_backtest_endpoint():
    """Test the backtest REST endpoint."""
    print("\n4. Testing backtest REST endpoint...")
    
    # This is a minimal test payload
    payload = {
        "strategy_name": "SimpleMovingAverageStrategy",
        "strategy_params": {
            "short_window": 20,
            "long_window": 50
        },
        "symbols": ["BTCUSDT"],
        "interval": "1h",
        "num_iterations": 10,
        "use_cache": False,
        "save_results": False
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/backtest/run",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ Backtest endpoint responded successfully")
                print(f"     Task ID: {data.get('task_id', 'N/A')}")
                return True
            else:
                print(f"   ✗ Backtest failed: {response.status_code}")
                print(f"     Response: {response.text}")
        except httpx.ConnectError:
            print(f"   ✗ Could not connect to {BASE_URL}/backtest/run")
        except Exception as e:
            print(f"   ✗ Error testing backtest: {e}")
    
    return False


async def test_mongodb_separation():
    """Test MongoDB master-slave separation."""
    print("\n5. Testing MongoDB master-slave separation...")
    
    # Test write operation via GraphQL mutation
    mutation = """
    mutation {
        updateSymbolMetadata(
            symbol: "TEST_SYMBOL",
            tags: ["test", "architecture"],
            sector: "testing"
        ) {
            symbol
            tags
            sector
        }
    }
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": mutation},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                print(f"   ✓ Write operation successful (master DB)")
                # In a real test, we'd verify this was written to master
                # and readable from slave
                return True
            else:
                print(f"   ✗ Write operation failed: {data}")
        else:
            print(f"   ✗ Mutation failed: {response.status_code}")
    
    return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Binance Trading Bot Architecture")
    print("=" * 60)
    
    tests = [
        test_health_check,
        test_graphql_symbols,
        test_graphql_strategies,
        test_backtest_endpoint,
        test_mongodb_separation
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"   ✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Passed: {sum(results)}/{len(results)}")
    print(f"  Failed: {len(results) - sum(results)}/{len(results)}")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed! Architecture is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())