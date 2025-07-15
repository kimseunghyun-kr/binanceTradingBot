from typing import Optional, Callable, List, Dict, Any
import pandas as pd

class TradeProposal:
    """
    Encapsulates a trade proposal (metadata + execution simulation logic).
    """
    def __init__(self, meta: TradeMeta, detail_df: pd.DataFrame):
        self.meta = meta
        self.detail_df = detail_df
        self._outcome = None

    def realize(
            self,
            add_buy_pct: float = 5.0,
            fee: float = 0.0,
            slippage: float = 0.0,
            execution_delay_bars: int = 0,
            crossing_policy: str = "prefer_sl",
            analytics_hook: Optional[Callable[[List[Dict[str, Any]], "TradeProposal"], None]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Simulate the outcome of a trade, supporting both LONG/SHORT, entry delay, DCA, and custom analytics.
        """
        if self._outcome is not None:
            return self._outcome

        df = self.detail_df
        if df.empty:
            self._outcome = None
            return None

        entry_idx = 0 + execution_delay_bars
        if entry_idx >= len(df):
            self._outcome = None
            return None

        is_short = (self.meta.direction.upper() == "SHORT")

        # Entry
        first_hour_open = df.iloc[entry_idx]["open"]
        real_entry_price = min(first_hour_open, self.meta.entry_price) * (1 + slippage) * (1 + fee)  # can use max() for shorts if you wish
        add_dca_price = real_entry_price * (1 + add_buy_pct / 100) if is_short else real_entry_price * (1 - add_buy_pct / 100)

        # TP and SL price logic
        if not is_short:
            tp_price = real_entry_price * (1 + (self.meta.tp_price - self.meta.entry_price) / self.meta.entry_price)
            sl_price = real_entry_price * (1 - (self.meta.entry_price - self.meta.sl_price) / self.meta.entry_price)
        else:
            # For SHORT: TP is "lower", SL is "higher"
            tp_price = real_entry_price * (1 - (self.meta.entry_price - self.meta.tp_price) / self.meta.entry_price)
            sl_price = real_entry_price * (1 + (self.meta.sl_price - self.meta.entry_price) / self.meta.entry_price)

        trades = [{
            'symbol': self.meta.symbol,
            'entry_time': int(df.iloc[entry_idx]['open_time']),
            'entry_price': real_entry_price,
            'trade_num': 1,
            'size': self.meta.size,
            'direction': self.meta.direction.upper()
        }]
        additional_dca_done = False

        for idx in range(entry_idx, len(df)):
            candle = df.iloc[idx]
            # DCA: add short if price rises for short, buy more if falls for long
            if not additional_dca_done:
                dca_trigger = candle['high'] >= add_dca_price if is_short else candle['low'] <= add_dca_price
                if dca_trigger:
                    trades.append({
                        'symbol': self.meta.symbol,
                        'entry_time': int(candle['open_time']),
                        'entry_price': add_dca_price * (1 + slippage) * (1 + fee),
                        'trade_num': 2,
                        'size': self.meta.size,
                        'direction': self.meta.direction.upper()
                    })
                    additional_dca_done = True

            # Crossing: both TP and SL hit in the same bar
            both_hit = (candle['low'] <= sl_price and candle['high'] >= tp_price) if not is_short \
                else (candle['high'] >= sl_price and candle['low'] <= tp_price)
            if both_hit:
                import random
                if crossing_policy == "prefer_sl":
                    result = "SL"
                elif crossing_policy == "prefer_tp":
                    result = "TP"
                elif crossing_policy == "random":
                    result = random.choice(["SL", "TP"])
                else:
                    result = "SL"
                chosen_price = sl_price if result == "SL" else tp_price
                chosen_exit_type = "SL" if result == "SL" else "TP"
                for trade in trades:
                    trade['exit_time'] = int(candle['open_time'])
                    trade['exit_price'] = chosen_price * (1 - slippage) * (1 - fee)
                    trade['return_pct'] = self._calc_return_pct(trade['entry_price'], trade['exit_price'], is_short)
                    trade['result'] = self._result_judge(trade['entry_price'], trade['exit_price'], is_short)
                    trade['exit_type'] = chosen_exit_type
                self._outcome = trades
                if analytics_hook: analytics_hook(trades, self)
                return trades

            # SL/TP single hit logic
            if (not is_short and candle['low'] <= sl_price) or (is_short and candle['high'] >= sl_price):
                for trade in trades:
                    trade['exit_time'] = int(candle['open_time'])
                    trade['exit_price'] = sl_price * (1 - slippage) * (1 - fee)
                    trade['return_pct'] = self._calc_return_pct(trade['entry_price'], trade['exit_price'], is_short)
                    trade['result'] = self._result_judge(trade['entry_price'], trade['exit_price'], is_short)
                    trade['exit_type'] = 'SL'
                self._outcome = trades
                if analytics_hook: analytics_hook(trades, self)
                return trades
            if (not is_short and candle['high'] >= tp_price) or (is_short and candle['low'] <= tp_price):
                for trade in trades:
                    trade['exit_time'] = int(candle['open_time'])
                    trade['exit_price'] = tp_price * (1 - slippage) * (1 - fee)
                    trade['return_pct'] = self._calc_return_pct(trade['entry_price'], trade['exit_price'], is_short)
                    trade['result'] = self._result_judge(trade['entry_price'], trade['exit_price'], is_short)
                    trade['exit_type'] = 'TP'
                self._outcome = trades
                if analytics_hook: analytics_hook(trades, self)
                return trades

        # No TP/SL hit, close at last candle
        last_candle = df.iloc[-1]
        last_close = last_candle['close'] * (1 - slippage) * (1 - fee)
        for trade in trades:
            trade['exit_time'] = int(last_candle['open_time'])
            trade['exit_price'] = last_close
            trade['return_pct'] = self._calc_return_pct(trade['entry_price'], trade['exit_price'], is_short)
            trade['result'] = self._result_judge(trade['entry_price'], trade['exit_price'], is_short)
            trade['exit_type'] = 'CLOSE'
        self._outcome = trades
        if analytics_hook: analytics_hook(trades, self)
        return trades

    @staticmethod
    def _calc_return_pct(entry_price: float, exit_price: float, is_short: bool) -> float:
        return ((exit_price - entry_price) / entry_price * 100) if not is_short else ((entry_price - exit_price) / entry_price * 100)

    @staticmethod
    def _result_judge(entry_price: float, exit_price: float, is_short: bool) -> str:
        if not is_short:
            return "WIN" if exit_price > entry_price else "LOSS"
        else:
            return "WIN" if exit_price < entry_price else "LOSS"
