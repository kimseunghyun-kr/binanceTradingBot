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

    def get_required_lookback(self) -> int:
        """
        Returns
        -------
        int
            The minimum number of historical bars (rows) required by this strategy
            to generate a valid trading signal in the decide() method.

        Explanation
        -----------
        - This should account for the largest indicator period (e.g., EMA200 needs at least 200 bars),
          plus any additional lookback the strategy logic requires.
        - For example, if your strategy uses both EMA15 and EMA33, return at least 33.
        - If your logic needs to access additional bars for safety (e.g., rolling calculations, edge cases),
          include those in the total.
        - This value is used by the backtest runner to:
            1. Ensure enough candle data is fetched and passed to each rolling window.
            2. Avoid errors from insufficient DataFrame length in the strategy.
        - You can override this method in child strategies to return a custom value.
        """
        return 35  # Default: matches legacy behavior. Override in subclasses for custom needs.

