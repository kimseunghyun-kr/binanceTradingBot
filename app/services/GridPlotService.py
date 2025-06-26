# app/services/gridplotservice.py

import itertools

from app.services.BackTestService import BacktestService
from app.utils.plot_results import plot_grid_search_3d

class GridPlotService:
    @staticmethod
    def run_grid_search(strategy, symbols, fetch_candles_func, param_grid, fixed_params, plot_dir):
        results = []
        keys = sorted(param_grid)
        combos = [dict(zip(keys, values)) for values in itertools.product(*(param_grid[k] for k in keys))]
        for params in combos:
            bt_params = {**fixed_params, **params}
            result = BacktestService.run_backtest(
                strategy,
                symbols,
                fetch_candles_func,
                interval=bt_params.get("interval"),
                num_iterations=bt_params.get("num_iterations", 100),
                tp_ratio=bt_params.get("tp_ratio", 0.1),
                sl_ratio=bt_params.get("sl_ratio", 0.05),
                save_charts=bt_params.get("save_charts", False),
                add_buy_pct=bt_params.get("add_buy_pct", 5.0),
                start_date=bt_params.get("start_date")
            )
            results.append((params, result.get("total_return_pct", 0)))
        plot_path = plot_grid_search_3d(results, plot_dir)
        return {"results": results, "plot_path": plot_path}
