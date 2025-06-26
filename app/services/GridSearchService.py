# app/services/GridSearchService.py

from itertools import product
from app.services.BackTestService import BacktestService
from app.marketDataApi.binance import fetch_candles
from app.services.StrategyService import StrategyService


class GridSearchService:
    @staticmethod
    def run_grid_search(strategy, timeframe, tp_list, sl_list, add_buy_pct_list,
                        num_iterations, use_cache, save_charts, start_date, symbols):
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
