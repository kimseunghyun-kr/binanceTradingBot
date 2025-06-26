import logging
from typing import Dict, Any, Optional, List

from app.marketDataApi.binance import fetch_candles
from app.marketDataApi.loader import initialize_symbols_from_config
from app.services.BackTestService import BacktestService
from app.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy


class CoordinatorService:
    def __init__(
        self,
        symbol_config: Optional[Dict[str, Any]] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        backtest_params: Optional[Dict[str, Any]] = None,
    ):
        self.symbol_config = symbol_config or {
            "mode": "filter_cmc",        # or "load_file"
            "min_cap": 150_000_000,
            "max_cap": 20_000_000_000,
            "max_pages": 5,
            "filename": "filtered_coins.txt"
        }
        self.strategy_params = strategy_params or {
            "recent_window": 7,
            "total_window": 200,
            "peak_ema_period": 15,
            "alt_ema_period": 33,
            "peak_pct": 1.2,
            "bearish_buffer": 0.1
        }
        self.backtest_params = backtest_params or {
            "interval": "1d",
            "num_iterations": 200,
            "tp_ratio": 0.1,
            "sl_ratio": 0.05,
            "save_charts": False,
            "add_buy_pct": 5.0,
            "start_date": None
        }

    def load_symbols(self) -> List[str]:
        mode = self.symbol_config.get("mode", "filter_cmc")
        if mode == "filter_cmc":
            symbols = initialize_symbols_from_config(self.symbol_config)
        elif mode == "load_file":
            symbols = initialize_symbols_from_config(self.symbol_config)
        else:
            raise ValueError(f"Unknown symbol load mode: {mode}")
        if not symbols:
            logging.error("No symbols loaded, aborting.")
            return []
        return symbols

    def run(self):
        logging.info("Coordinator starting symbol initialization.")
        symbols = self.load_symbols()
        if not symbols:
            print("No symbols found. Exiting.")
            return None

        logging.info(f"Coordinator loaded {len(symbols)} symbols. Instantiating strategy.")
        strategy = PeakEMAReversalStrategy(**self.strategy_params)

        logging.info("Coordinator starting backtest.")
        results = BacktestService.run_backtest(
            strategy,
            symbols,
            fetch_candles,
            interval=self.backtest_params["interval"],
            num_iterations=self.backtest_params["num_iterations"],
            tp_ratio=self.backtest_params["tp_ratio"],
            sl_ratio=self.backtest_params["sl_ratio"],
            save_charts=self.backtest_params["save_charts"],
            add_buy_pct=self.backtest_params["add_buy_pct"],
            start_date=self.backtest_params["start_date"],
        )
        return results
