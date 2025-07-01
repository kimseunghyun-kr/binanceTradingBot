import hashlib
import json
import logging
from typing import Dict, Any
from app.core.db import redis_cache


class BacktestService:
    _cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def generate_cache_key(symbols, interval, num_iterations, start_date, strategy_name,
                           tp_ratio, sl_ratio, add_buy_pct, save_charts):
        data = {
            "symbols": sorted(symbols),
            "interval": interval,
            "num_iterations": num_iterations,
            "start_date": start_date or "",
            "strategy": strategy_name,
            "tp": tp_ratio, "sl": sl_ratio, "add_buy_pct": add_buy_pct,
            "save_charts": bool(save_charts)
        }
        key_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    @classmethod
    def run_backtest(cls, strategy, symbols, fetch_candles_func, interval,
                     num_iterations=100, tp_ratio=0.1, sl_ratio=0.05, save_charts=False,
                     add_buy_pct=5.0, start_date=None,
                     use_cache: bool = True) -> Dict[str, Any]:
        """Run backtest on given symbols and return aggregated results."""
        print(tp_ratio, sl_ratio, add_buy_pct, save_charts, start_date)
        cache_key = cls.generate_cache_key(
            symbols, interval, num_iterations, start_date, strategy.__class__.__name__,
            tp_ratio, sl_ratio, add_buy_pct, save_charts
        )

        if use_cache:
            # Check Redis cache first
            if redis_cache:
                cached_json = redis_cache.get(cache_key)
                if cached_json:
                    logging.info(f"[BacktestService] Returning cached results from Redis for key {cache_key[:8]}...")
                    return json.loads(cached_json)
            # Fallback to in-memory cache
            if cache_key in cls._cache:
                logging.info(
                    f"[BacktestService] Using cached results for {strategy.__class__.__name__} {interval} on {len(symbols)} symbols.")
                return cls._cache[cache_key]

        # Initialize results structure
        results = {
            'trades': [], 'win_count': 0, 'loss_count': 0, 'error_count': 0,
            'total_return_pct': 0.0, 'max_drawdown_pct': 0.0, 'win_rate': 0.0,
            'avg_win_pct': 0.0, 'avg_loss_pct': 0.0, 'profit_factor': 0.0, 'equity_curve': []
        }
        all_trades = []
        # replace this sym in symbols to do a form of a sql query based on the ANALYSIS_SYMBOL
        # to get the required symbols
        # this method must be in Strategy Object.
        for sym in symbols:
            # honestly we should either have a list of indicators to be listed by the strategy to run through
            # individually in this function then pass them through or do these checks within the strategy_run
            df = fetch_candles_func(sym, interval, limit=num_iterations + 35)
            if df.empty or len(df) < 35:
                continue
            last_index = len(df) - 3
            first_index = max(35, last_index - (num_iterations - 1))
            for i in range(last_index, first_index - 1, -1):
                window_df = df.iloc[max(0, i - 34): i + 1].copy()
                decision = strategy.decide(window_df, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio)
                if decision.get('signal') != 'BUY':
                    continue
                entry_price = decision.get('entry_price')
                tp_price = decision.get('tp_price')
                sl_price = decision.get('sl_price')
                entry_time = int(df['open_time'].iloc[i])
                outcome = cls._simulate_trade(sym, entry_time, entry_price, tp_price, sl_price, interval,
                                              fetch_candles_func, save_charts, add_buy_pct)
                if outcome.get('error'):
                    results['error_count'] += 1
                    continue
                for trade in outcome['trades']:
                    trade_info = {
                        'symbol': sym,
                        'entry_time': trade['entry_time'],
                        'entry_price': trade['entry_price'],
                        'exit_time': trade['exit_time'],
                        'exit_price': trade['exit_price'],
                        'return_pct': trade['return_pct'],
                        'outcome': trade['result'],
                        'exit_type': trade['exit_type']
                    }
                    all_trades.append(trade_info)
                    results['trades'].append(trade_info)
                    if trade['result'] == 'WIN':
                        results['win_count'] += 1
                    elif trade['result'] == 'LOSS':
                        results['loss_count'] += 1
        # Compute stats
        if all_trades:
            all_trades.sort(key=lambda x: x['exit_time'])
            equity = 100.0
            equity_curve = [equity]
            max_equity = equity
            current_time = all_trades[0]['exit_time']
            current_group = []
            for trade in all_trades:
                if trade['exit_time'] != current_time:
                    if current_group:
                        avg_return = sum(t['return_pct'] for t in current_group) / len(current_group)
                        equity *= (1 + avg_return / 100.0)
                        equity_curve.append(equity)
                        max_equity = max(max_equity, equity)
                        current_group = []
                    current_time = trade['exit_time']
                current_group.append(trade)
            if current_group:
                avg_return = sum(t['return_pct'] for t in current_group) / len(current_group)
                equity *= (1 + avg_return / 100.0)
                equity_curve.append(equity)
                max_equity = max(max_equity, equity)
            results['equity_curve'] = equity_curve
            results['total_return_pct'] = equity - 100.0
            total_trades = results['win_count'] + results['loss_count']
            if total_trades > 0:
                results['win_rate'] = (results['win_count'] / total_trades) * 100.0
            win_returns = [t['return_pct'] for t in results['trades'] if t['outcome'] == 'WIN']
            loss_returns = [t['return_pct'] for t in results['trades'] if t['outcome'] == 'LOSS']
            if results['win_count'] > 0:
                results['avg_win_pct'] = sum(win_returns) / results['win_count']
            if results['loss_count'] > 0:
                results['avg_loss_pct'] = sum(abs(x) for x in loss_returns) / results['loss_count']
            if sum(abs(x) for x in loss_returns) > 0:
                results['profit_factor'] = sum(win_returns) / sum(abs(x) for x in loss_returns)
            else:
                results['profit_factor'] = None
            max_dd = 0.0
            peak_equity = equity_curve[0]
            for val in equity_curve:
                if val > peak_equity:
                    peak_equity = val
                drawdown_pct = (peak_equity - val) / peak_equity * 100.0
                if drawdown_pct > max_dd:
                    max_dd = drawdown_pct
            results['max_drawdown_pct'] = max_dd


        # Cache the results for future use
        if use_cache:
            cls._cache[cache_key] = results
            if redis_cache:
                try:
                    redis_cache.set(cache_key, json.dumps(results), ex=3600)  # cache for 1 hour (TTL configurable)
                except Exception as e:
                    logging.error(f"Redis caching failed: {e}")
        return results

    @staticmethod
    def _simulate_trade(symbol, entry_time, entry_price, tp_price, sl_price, main_interval, fetch_candles_func,
                        save_charts=False, add_buy_pct=5.0):
        detail_interval = "1h"
        num_candles = 48 if main_interval == "1d" else 336 if main_interval == "1w" else 48
        scan_df = fetch_candles_func(symbol, detail_interval, limit=300, start_time=entry_time)
        real_entry_time = entry_time
        for _, candle in scan_df.iterrows():
            if candle['low'] <= entry_price:
                real_entry_time = candle['open_time']
                break
        detailed_df = fetch_candles_func(symbol, detail_interval, limit=num_candles, start_time=real_entry_time)
        if detailed_df.empty:
            return {'trades': [], 'error': True}
        first_hour_open = detailed_df.iloc[0]["open"]
        real_entry_price = min(first_hour_open, entry_price)
        add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
        tp_price = real_entry_price * (1 + (tp_price - entry_price) / entry_price)
        sl_price = real_entry_price * (1 - (entry_price - sl_price) / entry_price)
        trades = []
        trades.append(
            {'entry_time': int(detailed_df.iloc[0]['open_time']), 'entry_price': real_entry_price, 'trade_num': 1})
        additional_buy_done = False
        avg_entry_price = real_entry_price
        for idx, candle in detailed_df.iterrows():
            if not additional_buy_done and candle['low'] <= add_buy_price:
                trades.append({'entry_time': int(candle['open_time']), 'entry_price': add_buy_price, 'trade_num': 2})
                additional_buy_done = True
                avg_entry_price = (real_entry_price * 0.25 + add_buy_price * 0.25) / 0.50
            if candle['low'] <= sl_price:
                for trade in trades:
                    trade['exit_time'] = int(candle['open_time'])
                    trade['exit_price'] = sl_price
                    trade['return_pct'] = ((sl_price - trade['entry_price']) / trade['entry_price']) * 100
                    trade['result'] = 'LOSS'
                    trade['exit_type'] = 'SL'
                return {'trades': trades, 'error': False}
            if candle['high'] >= tp_price:
                for trade in trades:
                    trade['exit_time'] = int(candle['open_time'])
                    trade['exit_price'] = tp_price
                    trade['return_pct'] = ((tp_price - trade['entry_price']) / trade['entry_price']) * 100
                    trade['result'] = 'WIN'
                    trade['exit_type'] = 'TP'
                return {'trades': trades, 'error': False}
        last_candle = detailed_df.iloc[-1]
        last_close = last_candle['close']
        for trade in trades:
            trade['exit_time'] = int(last_candle['open_time'])
            trade['exit_price'] = last_close
            trade['return_pct'] = ((last_close - trade['entry_price']) / trade['entry_price']) * 100
            trade['result'] = 'WIN' if last_close > trade['entry_price'] else 'LOSS'
            trade['exit_type'] = 'CLOSE'
        return {'trades': trades, 'error': False}
