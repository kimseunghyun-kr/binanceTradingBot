#!/usr/bin/env python3
"""
test_pure_function_basic.py
──────────────────────────────────────────────────────────────────────────
Basic test script to verify the pure function implementation works.
This script doesn't require pytest and can be run directly.
"""

import sys
import json
from datetime import datetime, timedelta


def test_prefetched_data_source():
    """Test PrefetchedDataSource class."""
    print("=" * 70)
    print("TEST: PrefetchedDataSource")
    print("=" * 70)

    from strategyOrchestrator.StrategyOrchestrator import PrefetchedDataSource

    # Create sample data
    candles = [
        {
            "open_time": i * 1000,
            "open": 100.0 + i,
            "high": 110.0 + i,
            "low": 90.0 + i,
            "close": 105.0 + i,
            "volume": 1000.0
        }
        for i in range(100)
    ]

    ohlcv_data = {
        "main": {"BTCUSDT": candles},
        "detailed": {}
    }

    source = PrefetchedDataSource(ohlcv_data)

    # Test fetching
    df = source.fetch_candles("BTCUSDT", "1d", limit=50)

    print(f"✓ Created PrefetchedDataSource")
    print(f"✓ Fetched {len(df)} candles (expected 50)")
    print(f"✓ Columns: {list(df.columns)}")
    print(f"✓ First close price: {df['close'].iloc[0]}")

    assert len(df) == 50, f"Expected 50 candles, got {len(df)}"
    assert "open_time" in df.columns, "Missing open_time column"
    assert "close" in df.columns, "Missing close column"

    print("\n✅ PrefetchedDataSource test PASSED\n")
    return True


def test_orchestrator_input_dto():
    """Test OrchestratorInput DTO with OHLCV data."""
    print("=" * 70)
    print("TEST: OrchestratorInput DTO")
    print("=" * 70)

    from app.dto.orchestrator.OrchestratorInput import (
        OrchestratorInput,
        StrategyParameters,
    )

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

    # Test with OHLCV data
    payload_with_data = orchestrator_input.to_container_payload(ohlcv_data=ohlcv_data)
    print(f"✓ Created OrchestratorInput")
    print(f"✓ Generated payload with OHLCV data")
    print(f"✓ Payload keys: {list(payload_with_data.keys())}")

    assert "ohlcv_data" in payload_with_data, "Missing ohlcv_data in payload"
    assert "symbols" in payload_with_data, "Missing symbols in payload"

    # Test without OHLCV data (legacy mode)
    payload_without_data = orchestrator_input.to_container_payload()
    print(f"✓ Generated payload without OHLCV data (legacy mode)")

    assert "ohlcv_data" not in payload_without_data, "ohlcv_data should not be in payload"

    print("\n✅ OrchestratorInput DTO test PASSED\n")
    return True


def test_json_serialization():
    """Test that OHLCV data can be properly serialized."""
    print("=" * 70)
    print("TEST: JSON Serialization")
    print("=" * 70)

    ohlcv_data = {
        "main": {
            "BTCUSDT": [
                {
                    "open_time": 1000,
                    "open": 100.0,
                    "high": 110.0,
                    "low": 90.0,
                    "close": 105.0,
                    "volume": 1000.0
                }
            ]
        },
        "detailed": {}
    }

    # Serialize
    json_str = json.dumps(ohlcv_data)
    print(f"✓ Serialized OHLCV data ({len(json_str)} chars)")

    # Deserialize
    deserialized = json.loads(json_str)
    print(f"✓ Deserialized OHLCV data")

    assert deserialized == ohlcv_data, "Deserialized data doesn't match original"

    print("\n✅ JSON Serialization test PASSED\n")
    return True


def test_container_config_pure():
    """Test that container config has no database credentials."""
    print("=" * 70)
    print("TEST: Container Config (Pure Function)")
    print("=" * 70)

    from app.services.orchestrator.OrchestratorService import OrchestratorService

    # Generate container config
    run_id = "test_run_12345678"
    config = OrchestratorService._container_config(run_id)

    env = config.get("environment", {})

    print(f"✓ Generated container config")
    print(f"✓ Environment variables: {list(env.keys())}")
    print(f"✓ Network mode: {config.get('network_mode')}")

    # Verify no database credentials
    forbidden_keys = ["MONGO_USER_PW", "MONGO_RO_URI", "MONGO_URI_SLAVE", "MONGO_DB_OHLCV"]
    for key in forbidden_keys:
        assert key not in env, f"Found forbidden key '{key}' in environment"
    print(f"✓ No database credentials in environment")

    # Verify network isolation
    assert config.get("network_mode") == "none", "Container should have network_mode='none'"
    print(f"✓ Container has no network access")

    # Verify mode is sandbox_pure
    assert env.get("KWONTBOT_MODE") == "sandbox_pure", "Mode should be 'sandbox_pure'"
    print(f"✓ Container mode is 'sandbox_pure'")

    print("\n✅ Container Config test PASSED\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("PURE FUNCTION ORCHESTRATOR - BASIC TESTS")
    print("=" * 70 + "\n")

    tests = [
        ("PrefetchedDataSource", test_prefetched_data_source),
        ("OrchestratorInput DTO", test_orchestrator_input_dto),
        ("JSON Serialization", test_json_serialization),
        ("Container Config", test_container_config_pure),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} test FAILED")
            print(f"Error: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!\n")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
