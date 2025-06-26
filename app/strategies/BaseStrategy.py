from typing import Any, Dict, Optional

import pandas as pd


class BaseStrategy:
    """
    Abstract base class for all strategies.
    """

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
