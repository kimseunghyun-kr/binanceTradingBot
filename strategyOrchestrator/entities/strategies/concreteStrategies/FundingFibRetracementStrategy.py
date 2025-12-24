from __future__ import annotations

from typing import Any, Dict, Optional
import threading

import pandas as pd

from strategyOrchestrator.entities.perpetuals.portfolio.Funding_repository import funding_provider
from strategyOrchestrator.entities.strategies.ParameterisedStrategy import ParametrizedStrategy


class FundingFibRetracementStrategy(ParametrizedStrategy):
    """
    Conditions (long bias):
      1) Funding rate is negative.
      2) Current pullback from recent peak is near a Fibonacci retracement
         of the prior larger upward wave.
      3) Current or previous candle volume is below the median of the
         retracement segment volume.
    """

    def __init__(
        self,
        peak_lookback: int = 30,
        wave_lookback: int = 120,
        fib_levels: Optional[list[float]] = None,
        fib_tolerance: float = 0.03,
        min_wave_pct: float = 0.03,
        volume_segment: str = "retracement",
        volume_lookback: int = 50,
        funding_threshold: float = 0.0,
        **kwargs,
    ):
        if fib_levels is None:
            fib_levels = [0.382, 0.5, 0.618]
        params = {
            "peak_lookback": peak_lookback,
            "wave_lookback": wave_lookback,
            "fib_levels": [float(x) for x in fib_levels],
            "fib_tolerance": float(fib_tolerance),
            "min_wave_pct": float(min_wave_pct),
            "volume_segment": volume_segment,
            "volume_lookback": int(volume_lookback),
            "funding_threshold": float(funding_threshold),
        }
        params.update(kwargs)
        super().__init__(**params)
        self._funding_cache: dict[tuple[str, int], float] = {}
        self._cache_lock = threading.Lock()

    def get_required_lookback(self) -> int:
        base = max(int(self.peak_lookback), int(self.wave_lookback))
        if self.volume_segment == "lookback":
            base = max(base, int(self.volume_lookback))
        return base + 2

    def decide(
        self,
        df: pd.DataFrame,
        interval: str,
        tp_ratio: float = 0.1,
        sl_ratio: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        symbol, sdf = self._select_symbol_frame(df)
        if sdf is None or sdf.empty:
            return self._no_signal()

        required_cols = {"high", "low", "close", "volume"}
        if not required_cols.issubset(sdf.columns):
            return self._no_signal()

        last_ts = self._latest_ts(sdf)
        if last_ts is None or symbol is None:
            return self._no_signal()

        funding_rate = self._get_funding_rate(symbol, last_ts)
        if funding_rate is None or funding_rate >= float(self.funding_threshold):
            return self._no_signal(meta={"funding_rate": funding_rate})

        if len(sdf) < self.get_required_lookback():
            return self._no_signal(meta={"funding_rate": funding_rate})

        peak_pos, peak_price = self._recent_peak(sdf)
        if peak_pos is None:
            return self._no_signal(meta={"funding_rate": funding_rate})

        wave_low_pos, wave_low = self._wave_low_before_peak(sdf, peak_pos)
        if wave_low_pos is None or wave_low <= 0:
            return self._no_signal(meta={"funding_rate": funding_rate})

        wave_range = peak_price - wave_low
        if wave_range <= 0:
            return self._no_signal(meta={"funding_rate": funding_rate})

        wave_pct = wave_range / wave_low
        if wave_pct < float(self.min_wave_pct):
            return self._no_signal(meta={"funding_rate": funding_rate})

        current_price = float(sdf["close"].iloc[-1])
        if current_price >= peak_price:
            return self._no_signal(meta={"funding_rate": funding_rate})

        retracement = (peak_price - current_price) / wave_range
        if not (0.0 < retracement < 1.0):
            return self._no_signal(meta={"funding_rate": funding_rate, "retracement": retracement})

        matched_level = self._match_fib_level(retracement)
        if matched_level is None:
            return self._no_signal(meta={"funding_rate": funding_rate, "retracement": retracement})

        median_volume = self._segment_median_volume(sdf, wave_low_pos, peak_pos)
        if median_volume is None:
            return self._no_signal(meta={"funding_rate": funding_rate})

        curr_vol = float(sdf["volume"].iloc[-1])
        prev_vol = float(sdf["volume"].iloc[-2]) if len(sdf) > 1 else curr_vol
        if not (curr_vol <= median_volume or prev_vol <= median_volume):
            return self._no_signal(
                meta={"funding_rate": funding_rate, "median_volume": median_volume}
            )

        entry_price = current_price
        tp_price = entry_price * (1 + tp_ratio)
        sl_price = entry_price * (1 - sl_ratio)

        return {
            "signal": "BUY",
            "entry_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "confidence": None,
            "meta": {
                "funding_rate": funding_rate,
                "retracement": retracement,
                "fib_level": matched_level,
                "peak_price": peak_price,
                "wave_low": wave_low,
                "median_volume": median_volume,
                "volume_segment": self.volume_segment,
            },
            "strategy_name": "FundingFibRetracementStrategy",
            "decision": f"YES_{matched_level}",
            "direction": "LONG",
        }

    def _select_symbol_frame(self, df: pd.DataFrame) -> tuple[Optional[str], Optional[pd.DataFrame]]:
        if isinstance(df.columns, pd.MultiIndex):
            symbols = df.columns.get_level_values(0).unique().tolist()
            if not symbols:
                return None, None
            symbol = symbols[0]
            return symbol, df[symbol]
        symbol = None
        if "symbol" in df.columns:
            try:
                symbol = str(df["symbol"].iloc[-1])
            except Exception:
                symbol = None
        return symbol, df

    def _latest_ts(self, df: pd.DataFrame) -> Optional[int]:
        if "open_time" in df.columns:
            try:
                return int(df["open_time"].iloc[-1])
            except Exception:
                return None
        return None

    def _get_funding_rate(self, symbol: str, ts: int) -> Optional[float]:
        key = (symbol, ts)
        with self._cache_lock:
            if key in self._funding_cache:
                return self._funding_cache[key]

        rate = funding_provider.get_rate(symbol, ts)
        alt_ts = ts // 1000
        if rate == 0.0 and alt_ts != ts:
            alt_rate = funding_provider.get_rate(symbol, alt_ts)
            if alt_rate != 0.0:
                rate = alt_rate

        with self._cache_lock:
            self._funding_cache[key] = rate
        return rate

    def _recent_peak(self, df: pd.DataFrame) -> tuple[Optional[int], Optional[float]]:
        n = len(df)
        peak_lookback = max(1, int(self.peak_lookback))
        start = max(0, n - peak_lookback)
        highs = df["high"].to_numpy()
        peak_pos = int(highs[start:].argmax()) + start
        if peak_pos >= n - 1:
            return None, None
        return peak_pos, float(highs[peak_pos])

    def _wave_low_before_peak(
        self, df: pd.DataFrame, peak_pos: int
    ) -> tuple[Optional[int], Optional[float]]:
        wave_lookback = max(1, int(self.wave_lookback))
        start = max(0, peak_pos - wave_lookback + 1)
        lows = df["low"].to_numpy()
        slice_lows = lows[start:peak_pos + 1]
        if slice_lows.size == 0:
            return None, None
        low_pos = int(slice_lows.argmin()) + start
        if low_pos >= peak_pos:
            return None, None
        return low_pos, float(lows[low_pos])

    def _match_fib_level(self, retracement: float) -> Optional[float]:
        for level in self.fib_levels:
            if abs(retracement - float(level)) <= float(self.fib_tolerance):
                return float(level)
        return None

    def _segment_median_volume(
        self,
        df: pd.DataFrame,
        wave_low_pos: int,
        peak_pos: int,
    ) -> Optional[float]:
        if self.volume_segment == "wave":
            segment = df["volume"].iloc[wave_low_pos:peak_pos + 1]
        elif self.volume_segment == "lookback":
            segment = df["volume"].iloc[-int(self.volume_lookback):]
        else:
            segment = df["volume"].iloc[peak_pos:]
        if segment.empty:
            return None
        return float(segment.median())

    def _no_signal(self, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "signal": "NO",
            "entry_price": None,
            "tp_price": None,
            "sl_price": None,
            "confidence": 0,
            "meta": meta or {},
            "strategy_name": "FundingFibRetracementStrategy",
        }
