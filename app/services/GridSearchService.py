# app/services/GridSearchService.py

from itertools import product
from typing import Optional

from app.marketDataApi.binance import fetch_candles
from app.services.BackTestService import BacktestService
from app.services.StrategyService import StrategyService


class GridSearchService:
    @staticmethod
    def run_grid_search(strategy: dict, timeframe: str, tp_list: list, sl_list: list, add_buy_pct_list: list,
                        num_iterations: int, use_cache: bool, save_charts: bool,
                        start_date: Optional[str], symbols: list):
        """Run a parameter grid search for the given strategy."""
        # Prepare strategy instance, including sub-strategies if any
        strategy_name = strategy["name"]
        # Construct params dict with possible 'strategies' list for ensemble
        strat_params = {
            "params": strategy.get("params", {}) or {},
            "strategies": strategy.get("strategies", []) or []
        }
        try:
            strategy_instance = StrategyService.get_strategy_instance(strategy_name, strat_params)
        except ValueError as e:
            # Unknown strategy or missing sub-strategies
            raise e

        # Expand grid
        combos = list(product(tp_list, sl_list, add_buy_pct_list))
        results = []
        strategy_instance = StrategyService.get_strategy_instance(strategy["name"], strategy.get("params", {}))
        for tp, sl, add_buy in combos:
            result = BacktestService.run_backtest(
                strategy_instance, symbols, fetch_candles,
                interval=timeframe, num_iterations=num_iterations,
                tp_ratio=tp, sl_ratio=sl,
                save_charts=save_charts, add_buy_pct=add_buy, start_date=start_date
            )
            results.append({"tp": tp, "sl": sl, "add_buy": add_buy, "result": result})
        # (optionally generate a 3D plot here)
        return results
