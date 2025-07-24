#!/usr/bin/env python3
"""
Test script to verify backtest functionality
"""

import requests
import json
import time

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_backtest():
    """Test a simple backtest execution"""
    
    # Backtest request payload
    payload = {
        "strategy_name": "peak_ema_reversal",
        "strategy_params": {
            "tp_ratio": 0.1,
            "sl_ratio": 0.05
        },
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "interval": "1h",
        "num_iterations": 10,  # Small number for testing
        "use_cache": False,
        "save_results": True,
        "stream_progress": False,
        "initial_capital": 10000.0,
        "position_size_pct": 5.0,
        "max_positions": 10,
        "tp_ratio": 0.1,
        "sl_ratio": 0.05
    }
    
    print("Submitting backtest...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Submit backtest
    response = requests.post(
        f"{BASE_URL}/backtest/submit-test",
        json=payload
    )
    
    if response.status_code != 200:
        print(f"Error submitting backtest: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    task_id = result["task_id"]
    print(f"Backtest submitted successfully!")
    print(f"Task ID: {task_id}")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    
    # Poll for results
    print("\nPolling for results...")
    max_attempts = 60  # 5 minutes max
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(5)  # Wait 5 seconds between polls
        
        # Check status
        status_response = requests.get(f"{BASE_URL}/backtest/status/{task_id}")
        
        if status_response.status_code != 200:
            print(f"Error checking status: {status_response.status_code}")
            break
        
        status_data = status_response.json()
        state = status_data.get("state")
        
        print(f"[{attempt+1}/{max_attempts}] State: {state}", end="")
        
        if state == "PROGRESS":
            progress = status_data.get("progress", 0)
            current = status_data.get("current", "")
            print(f" - Progress: {progress}% - Current: {current}")
        elif state == "SUCCESS":
            print(" - Completed!")
            
            # Get full results
            results_response = requests.get(f"{BASE_URL}/backtest/results/{task_id}")
            if results_response.status_code == 200:
                results = results_response.json()
                print(f"\nBacktest Results:")
                print(f"Total trades: {results.get('total_trades', 0)}")
                print(f"Win rate: {results.get('win_rate', 0):.2%}")
                print(f"Total return: {results.get('total_return_pct', 0):.2%}")
            break
        elif state == "FAILURE":
            error = status_data.get("error", "Unknown error")
            print(f" - Failed: {error}")
            if "traceback" in status_data:
                print(f"Traceback:\n{status_data['traceback']}")
            break
        else:
            print()
        
        attempt += 1
    
    if attempt >= max_attempts:
        print("\nTimeout waiting for results")

def test_api_health():
    """Test if the API is running"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("API is running!")
            return True
        else:
            print(f"API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("Cannot connect to API. Make sure the server is running.")
        return False

if __name__ == "__main__":
    print("Testing Binance Trading Bot Backtest API")
    print("=" * 50)
    
    if test_api_health():
        print("\nStarting backtest test...")
        test_backtest()
    else:
        print("\nPlease start the API server first:")
        print("  python run_local.py")