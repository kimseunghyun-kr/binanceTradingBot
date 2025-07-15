import logging
from typing import List, Tuple

from app.marketDataApi.binance import fetch_candles
from entities.strategies.BaseStrategy import BaseStrategy
from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy


class AnalysisService:
    """Service for running current market analysis on a list of symbols."""

    @staticmethod
    def analyze_symbols(strategy: BaseStrategy = PeakEMAReversalStrategy(), symbols: List[str] = [],
                        interval: str = "1d") -> Tuple[List[str], int]:
        """
        Analyze each symbol for a buy signal using PeakEMAReversalStrategy (default).
        Returns a tuple (yes_signals, no_count):
          - yes_signals: list of strings like "SYMBOL(EMA_period)" for each buy signal detected.
          - no_count: number of symbols with no buy signal.
        """
        yes_signals = []
        no_count = 0
        for sym in symbols:
            # Fetch latest 100 candles for analysis
            df = fetch_candles(sym, interval, limit=100)
            if df.empty:
                logging.info(f"[AnalysisService] No data for {sym} on interval {interval}. Skipping.")
                continue
            decision = strategy.decide(df, interval)
            decision_str = decision.get('decision', 'NO')
            if decision_str.startswith("YES"):
                yes_signals.append(f"{sym}({decision_str.split('_')[-1]})")
            else:
                no_count += 1
        return yes_signals, no_count
