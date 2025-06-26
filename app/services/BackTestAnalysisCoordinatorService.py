import logging
from typing import Dict, Any, Optional, List, Tuple

from app.marketDataApi.binance import fetch_candles
from app.marketDataApi.loader import initialize_symbols_from_config
from app.services.BackTestService import BacktestService
from app.services.AnalysisService import AnalysisService  # Assuming you have this
from app.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy

class BacktestAnalysisCoordinator:
    def __init__(
        self,
        symbol_config: Optional[Dict[str, Any]] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
        backtest_params: Optional[Dict[str, Any]] = None,
        analysis_params: Optional[Dict[str, Any]] = None,
    ):
        self.symbol_config = symbol_config or {
            "mode": "filter_cmc",
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
        self.analysis_params = analysis_params or {
            "interval": "1d",
        }

    def load_symbols(self) -> List[str]:
        mode = self.symbol_config.get("mode", "filter_cmc")
        symbols = initialize_symbols_from_config(self.symbol_config)
        if not symbols:
            logging.error("No symbols loaded, aborting.")
            return []
        return symbols

    def run_analysis(self, symbols: List[str], strategy=None) -> Tuple[List[str], int]:
        interval = self.analysis_params.get("interval", "1d")
        # You can inject a strategy here if you want advanced analysis
        yes_signals, no_count = AnalysisService.analyze_symbols(symbols, interval=interval)
        return yes_signals, no_count

    def run_backtest(self, symbols: List[str], strategy):
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

    def run(self):
        logging.info("BacktestAnalysisCoordinator starting symbol initialization.")
        symbols = self.load_symbols()
        if not symbols:
            print("No symbols found. Exiting.")
            return None

        # INSTANTIATE STRATEGY
        logging.info(f"Loaded {len(symbols)} symbols. Instantiating strategy.")
        strategy = PeakEMAReversalStrategy(**self.strategy_params)

        # 1. ANALYSIS (CURRENT BUY SIGNALS)
        logging.info("Running current market analysis (live signals)...")
        yes_signals, no_count = self.run_analysis(symbols, strategy=strategy)
        logging.info(f"Buy signals found: {yes_signals}")
        logging.info(f"No signal count: {no_count}")

        # 2. BACKTEST (HISTORICAL PERFORMANCE)
        logging.info("Running backtest (historical performance)...")
        results = self.run_backtest(symbols, strategy)
        logging.info("Backtest results computed.")

        # RETURN BOTH FOR FURTHER REPORTING/USAGE
        return {
            "analysis_signals": yes_signals,
            "analysis_no_count": no_count,
            "backtest_results": results,
        }
