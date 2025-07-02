from typing import Any, Dict, Optional, List

import pandas as pd


class BaseStrategy:
    """
    Abstract base class for all strategies.
    """

    def filter_symbols(self, symbols_df: pd.DataFrame) -> List[str]:
        """
        (Optional) Return a subset of symbols for this strategy.
        Default: use all symbols in symbols_df.
        """
        return symbols_df['symbol'].tolist()

    def aggregate_signals(self, trades: List[Dict[str, Any]]) -> Any:
        """
        (Optional) Combine or select among multiple trade signals.
        Default: no aggregation (pass through list of trades).
        """
        return trades

    def required_indicators(self) -> List[str]:
        """
        (Optional) List any technical indicators the strategy needs (e.g. ["EMA", "RSI"]).
        """
        return []

    def decide(self, df: pd.DataFrame, interval: str, **kwargs) -> Dict[str, Any]:
        """
        Args:
            df: pd.DataFrame of candles (OHLCV)
            interval: e.g. '1w', '1d'
            **kwargs: extra params
        Returns:
            dict with at least keys: signal, entry_price, tp_price, sl_price, confidence, meta, strategy_name
        """
        raise NotImplementedError("Each strategy must implement the decide method.")

    def fit(self, data: Optional[Any] = None):
        """
        Optional: Fit/train on historical data, if applicable (e.g., ML strategies).
        """
        pass

    def reset(self):
        """
        Optional: Reset any state.
        """
        pass

    def set_params(self, **params):
        """
        Set strategy-specific params (TP, SL, thresholds, etc.)
        """
        for k, v in params.items():
            setattr(self, k, v)

    def get_params(self):
        """
        Get strategy parameters for logging/tuning.
        """
        return self.__dict__

        # ...

    def get_required_lookback(self) -> int:
        """
        How many historical bars this strategy requires per run.
        Override if more are needed (e.g., for long EMA).
        """
        return max([period for period in self.get_indicator_periods()] + [35])

    def get_indicator_periods(self) -> list:
        """
        Override this to return all periods required by indicators (e.g., [15, 33, 50]).
        """
        return [35]  # Default fallback
