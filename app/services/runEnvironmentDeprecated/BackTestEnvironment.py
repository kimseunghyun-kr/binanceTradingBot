import hashlib
import json
import logging
from typing import List, Dict

import pandas as pd

from app.analysis.analyzeData import plot_and_save_chart
from app.marketDataApi.binance import fetch_candles

# Caching
_SIGNALS_CACHE = {}


def generate_cache_key(symbols: List[str], interval: str, num_iterations: int, start_date: str = None) -> str:
    cache_data = {
        'symbols': sorted(symbols),
        'interval': interval,
        'num_iterations': num_iterations,
        'start_date': start_date
    }
    cache_str = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_str.encode()).hexdigest()


def analyze_backtest_candle(strategy, df: pd.DataFrame, i: int, interval: str, tp_ratio: float = 0.1,
                            sl_ratio: float = 0.05) -> dict:
    start_i = max(0, i - 34)
    sub_df = df.iloc[start_i: i + 1].copy()
    if len(sub_df) < 35:
        return {'signal': 'NO'}
    return strategy.decide(sub_df, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio)


def collect_signals_and_data(
        strategy,
        symbols: List[str],
        interval: str,
        num_iterations: int,
        start_date: str = None
) -> List[Dict]:
    logging.info(f"Collecting signals and fetching marketDataApi for {interval} (cache miss)...")
    signals = []

    for sym in symbols:
        if start_date:
            desired_analysis_start_dt = pd.Timestamp(start_date)
            offset_periods = 35
            fetch_start_dt = desired_analysis_start_dt
            if interval == "1w":
                fetch_start_dt -= pd.Timedelta(weeks=offset_periods)
            elif interval == "1d":
                fetch_start_dt -= pd.Timedelta(days=offset_periods)
            else:
                logging.warning(f"Unhandled interval '{interval}' for fetch start_date offset.")
            api_start_ts = int(fetch_start_dt.timestamp() * 1000)
            df = fetch_candles(sym, interval, limit=2000, start_time=api_start_ts)
            if df.empty or len(df) <= offset_periods:
                continue
            first_start = 35
            last_start = min(len(df) - 3, first_start + num_iterations - 1)
            for i in range(first_start, last_start + 1):
                trade = analyze_backtest_candle(strategy, df, i, interval)
                if trade['signal'] == 'BUY':
                    entry_time = df['open_time'].iloc[i]
                    real_entry_time, detailed_df = find_real_entry_time(
                        sym, entry_time, trade['entry_price'], interval
                    )
                    signal_data = {
                        'symbol': sym,
                        'backtest_index': i,
                        'initial_entry_time': entry_time,
                        'initial_entry_price': trade['entry_price'],
                        'real_entry_time': real_entry_time,
                        'detailed_df': detailed_df,
                        'main_df': df
                    }
                    signals.append(signal_data)
        else:
            df = fetch_candles(sym, interval, limit=num_iterations + 35)
            if df.empty or len(df) < 35:
                continue
            last_start = len(df) - 3
            first_start = last_start - (num_iterations - 1)
            if first_start < 35:
                first_start = 35
            for i in range(last_start, first_start - 1, -1):
                trade = analyze_backtest_candle(strategy, df, i, interval)
                if trade['signal'] == 'BUY':
                    entry_time = df['open_time'].iloc[i]
                    real_entry_time, detailed_df = find_real_entry_time(
                        sym, entry_time, trade['entry_price'], interval
                    )
                    signal_data = {
                        'symbol': sym,
                        'backtest_index': i,
                        'initial_entry_time': entry_time,
                        'initial_entry_price': trade['entry_price'],
                        'real_entry_time': real_entry_time,
                        'detailed_df': detailed_df,
                        'main_df': df
                    }
                    signals.append(signal_data)
    logging.info(f"Collected {len(signals)} buy signals with pre-fetched marketDataApi")
    return signals


def clear_signals_cache():
    global _SIGNALS_CACHE
    _SIGNALS_CACHE.clear()
    logging.info("Signals cache cleared")


def get_cache_info():
    global _SIGNALS_CACHE
    if not _SIGNALS_CACHE:
        return "Cache is empty"
    info = []
    for cache_key, signals in _SIGNALS_CACHE.items():
        info.append(f"Cache key: {cache_key[:8]}... - {len(signals)} signals")
    return "\n".join(info)


def get_detail_timeframe_params(main_interval: str) -> tuple:
    if main_interval == "1w":
        return "1h", 336
    elif main_interval == "1d":
        return "1h", 48
    return "1h", 48


def find_real_entry_time(
        symbol: str,
        initial_entry_time: int,
        entry_price: float,
        main_interval: str,
        scan_limit: int = 300
) -> tuple:
    detail_interval, num_candles = get_detail_timeframe_params(main_interval)
    scan_df = fetch_candles(
        symbol,
        detail_interval,
        limit=scan_limit,
        start_time=initial_entry_time
    )
    real_entry_time = initial_entry_time
    for _, candle in scan_df.iterrows():
        if candle['low'] <= entry_price:
            real_entry_time = candle['open_time']
            break
    detail_df = fetch_candles(
        symbol,
        detail_interval,
        limit=num_candles,
        start_time=real_entry_time
    )
    return real_entry_time, detail_df


def simulate_trade_outcome(
        symbol: str,
        entry_time: int,
        entry_price: float,
        tp_price: float,
        sl_price: float,
        main_interval: str,
        save_charts: bool = False,
        add_buy_pct: float = 5.0
) -> dict:
    detail_interval, num_candles = get_detail_timeframe_params(main_interval)
    scan_df = fetch_candles(
        symbol,
        detail_interval,
        limit=300,
        start_time=entry_time
    )
    real_entry_time = entry_time
    for _, candle in scan_df.iterrows():
        if candle['low'] <= entry_price:
            real_entry_time = candle['open_time']
            break
    detailed_df = fetch_candles(
        symbol,
        detail_interval,
        limit=num_candles,
        start_time=real_entry_time
    )
    if detailed_df.empty:
        return {'trades': [], 'error': True}
    first_hour_open = detailed_df.iloc[0]["open"]
    real_entry_price = min(first_hour_open, entry_price)
    add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
    tp_price = real_entry_price * (1 + (tp_price - entry_price) / entry_price)
    sl_price = real_entry_price * (1 - (entry_price - sl_price) / entry_price)
    trades = []
    first_trade = {
        'entry_time': int(detailed_df.iloc[0]['open_time']),
        'entry_price': real_entry_price,
        'trade_num': 1
    }
    trades.append(first_trade)
    additional_buy_done = False
    total_position = 0.25
    avg_entry_price = real_entry_price
    for idx, candle in detailed_df.iterrows():
        if not additional_buy_done and candle['low'] <= add_buy_price:
            additional_trade = {
                'entry_time': int(candle['open_time']),
                'entry_price': add_buy_price,
                'trade_num': 2
            }
            trades.append(additional_trade)
            additional_buy_done = True
            total_position = 0.50
            avg_entry_price = (real_entry_price * 0.25 + add_buy_price * 0.25) / 0.50
        if candle['low'] <= sl_price:
            for trade in trades:
                trade['exit_time'] = int(candle['open_time'])
                trade['exit_price'] = sl_price
                trade['return_pct'] = ((sl_price - trade['entry_price']) / trade['entry_price']) * 100
                trade['result'] = 'LOSS'
                trade['exit_type'] = 'SL'
            if save_charts:
                plot_and_save_chart(
                    df_100=detailed_df,
                    symbol=symbol,
                    interval=detail_interval,
                    backtest_index=None,
                    is_detail_tf=True,
                    entry_price=avg_entry_price,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
            return {'trades': trades, 'error': False}
        if candle['high'] >= tp_price:
            for trade in trades:
                trade['exit_time'] = int(candle['open_time'])
                trade['exit_price'] = tp_price
                trade['return_pct'] = ((tp_price - trade['entry_price']) / trade['entry_price']) * 100
                trade['result'] = 'WIN'
                trade['exit_type'] = 'TP'
            if save_charts:
                plot_and_save_chart(
                    df_100=detailed_df,
                    symbol=symbol,
                    interval=detail_interval,
                    backtest_index=None,
                    is_detail_tf=True,
                    entry_price=avg_entry_price,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
            return {'trades': trades, 'error': False}
    last_candle = detailed_df.iloc[-1]
    last_close = last_candle['close']
    for trade in trades:
        trade['exit_time'] = int(last_candle['open_time'])
        trade['exit_price'] = last_close
        trade['return_pct'] = ((last_close - trade['entry_price']) / trade['entry_price']) * 100
        trade['result'] = 'WIN' if last_close > trade['entry_price'] else 'LOSS'
        trade['exit_type'] = 'CLOSE'
    if save_charts:
        plot_and_save_chart(
            df_100=detailed_df,
            symbol=symbol,
            interval=detail_interval,
            backtest_index=None,
            is_detail_tf=True,
            entry_price=avg_entry_price,
            tp_price=tp_price,
            sl_price=sl_price
        )
    return {'trades': trades, 'error': False}


def simulate_trade_outcome_cached(
        signal_data: Dict,
        tp_ratio: float,
        sl_ratio: float,
        add_buy_pct: float,
        save_charts: bool = False
) -> dict:
    detailed_df = signal_data['detailed_df']
    symbol = signal_data['symbol']
    initial_entry_price = signal_data['initial_entry_price']
    if detailed_df.empty:
        return {'trades': [], 'error': True}
    first_hour_open = detailed_df.iloc[0]["open"]
    real_entry_price = min(first_hour_open, initial_entry_price)
    tp_price = real_entry_price * (1 + tp_ratio)
    sl_price = real_entry_price * (1 - sl_ratio)
    add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
    trades = []
    first_trade = {
        'entry_time': int(detailed_df.iloc[0]['open_time']),
        'entry_price': real_entry_price,
        'trade_num': 1
    }
    trades.append(first_trade)
    additional_buy_done = False
    for idx, candle in detailed_df.iterrows():
        if not additional_buy_done and candle['low'] <= add_buy_price:
            additional_trade = {
                'entry_time': int(candle['open_time']),
                'entry_price': add_buy_price,
                'trade_num': 2
            }
            trades.append(additional_trade)
            additional_buy_done = True
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


def backtest_timeframe(
        strategy,
        symbols: List[str],
        interval: str,
        num_iterations: int,
        tp_ratio: float = 0.1,
        sl_ratio: float = 0.05,
        save_charts: bool = False,
        add_buy_pct: float = 5.0,
        start_date: str = None
) -> dict:
    logging.info(f"Starting backtest for {interval} ...")
    results = {
        'trades': [],
        'win_count': 0,
        'loss_count': 0,
        'error_count': 0,
        'total_return_pct': 0.0,
        'max_drawdown_pct': 0.0,
        'win_rate': 0.0,
        'avg_win_pct': 0.0,
        'avg_loss_pct': 0.0,
        'profit_factor': 0.0,
        'equity_curve': []
    }
    all_trades = []
    for sym in symbols:
        if start_date:
            desired_analysis_start_dt = pd.Timestamp(start_date)
            offset_periods = 35
            fetch_start_dt = desired_analysis_start_dt
            if interval == "1w":
                fetch_start_dt -= pd.Timedelta(weeks=offset_periods)
            elif interval == "1d":
                fetch_start_dt -= pd.Timedelta(days=offset_periods)
            else:
                logging.warning(
                    f"Unhandled interval '{interval}' for fetch start_date offset. Using desired_analysis_start_dt as fetch start.")
            api_start_ts = int(fetch_start_dt.timestamp() * 1000)
            logging.info(
                f"Fetching marketDataApi for {sym} ({interval}) from {fetch_start_dt.strftime('%Y-%m-%d')} for desired analysis start {start_date}")
            df = fetch_candles(sym, interval, limit=2000, start_time=api_start_ts)
            if df.empty or len(df) <= offset_periods:
                logging.warning(
                    f"Skipping {sym} ({interval}), insufficient marketDataApi from {fetch_start_dt.strftime('%Y-%m-%d')} (got {len(df) if not df.empty else 0} candles, need > {offset_periods}) for desired analysis start {start_date}.")
                continue
            first_start = 35
            last_start = min(len(df) - 3, first_start + num_iterations - 1)
            for i in range(first_start, last_start + 1):
                trade = analyze_backtest_candle(strategy, df, i, interval, tp_ratio, sl_ratio)
                if trade['signal'] == 'BUY':
                    entry_price = trade['entry_price']
                    tp_price = trade['tp_price']
                    sl_price = trade['sl_price']
                    entry_time = df['open_time'].iloc[i]
                    outcome = simulate_trade_outcome(
                        sym, entry_time, entry_price, tp_price, sl_price,
                        interval, save_charts, add_buy_pct
                    )
                    if outcome['error']:
                        logging.error(f"Error in trade simulation for {sym} at {interval} at index {i}")
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
                        else:
                            results['error_count'] += 1
                    if save_charts:
                        plot_and_save_chart(
                            df_100=df,
                            symbol=sym,
                            interval=interval,
                            backtest_index=i,
                            is_detail_tf=False
                        )
        else:
            df = fetch_candles(sym, interval, limit=num_iterations + 35)
            if df.empty or len(df) < 35:
                logging.info(f"Skipping {sym} at {interval}, insufficient marketDataApi.")
                continue
            last_start = len(df) - 3
            first_start = last_start - (num_iterations - 1)
            if first_start < 35:
                first_start = 35
            for i in range(last_start, first_start - 1, -1):
                trade = analyze_backtest_candle(strategy, df, i, interval, tp_ratio, sl_ratio)
                if trade['signal'] == 'BUY':
                    entry_price = trade['entry_price']
                    tp_price = trade['tp_price']
                    sl_price = trade['sl_price']
                    entry_time = df['open_time'].iloc[i]
                    outcome = simulate_trade_outcome(
                        sym, entry_time, entry_price, tp_price, sl_price,
                        interval, save_charts, add_buy_pct
                    )
                    if outcome['error']:
                        logging.error(f"Error in trade simulation for {sym} at {interval} at index {i}")
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
                        else:
                            results['error_count'] += 1
                    if save_charts:
                        plot_and_save_chart(
                            df_100=df,
                            symbol=sym,
                            interval=interval,
                            backtest_index=i,
                            is_detail_tf=False
                        )
    all_trades.sort(key=lambda x: x['exit_time'])
    equity = 100.0
    equity_curve = [equity]
    max_equity = equity
    current_trades = []
    current_time = None
    for trade in all_trades:
        if current_time != trade['exit_time']:
            if current_trades:
                avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
                equity *= (1 + avg_return / 100)
                equity_curve.append(equity)
                max_equity = max(max_equity, equity)
                current_drawdown = ((max_equity - equity) / max_equity) * 100
                results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
            current_trades = [trade]
            current_time = trade['exit_time']
        else:
            current_trades.append(trade)
    if current_trades:
        avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
        equity *= (1 + avg_return / 100)
        equity_curve.append(equity)
        max_equity = max(max_equity, equity)
        current_drawdown = ((max_equity - equity) / max_equity) * 100
        results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
    total_trades = results['win_count'] + results['loss_count']
    if total_trades > 0:
        results['win_rate'] = (results['win_count'] / total_trades) * 100
        results['total_return_pct'] = ((equity_curve[-1] / equity_curve[0]) - 1) * 100
        win_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'WIN']
        loss_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'LOSS']
        if win_returns:
            results['avg_win_pct'] = sum(win_returns) / len(win_returns)
        if loss_returns:
            results['avg_loss_pct'] = sum(loss_returns) / len(loss_returns)
        total_wins = sum(win_returns) if win_returns else 0
        total_losses = abs(sum(loss_returns)) if loss_returns else 0
        results['profit_factor'] = total_wins / total_losses if total_losses != 0 else float('inf')
    results['equity_curve'] = equity_curve
    return results


def backtest_timeframe_cached(
        strategy,
        symbols: List[str],
        interval: str,
        num_iterations: int,
        tp_ratio: float = 0.1,
        sl_ratio: float = 0.05,
        save_charts: bool = False,
        add_buy_pct: float = 5.0,
        start_date: str = None
) -> dict:
    cache_key = generate_cache_key(symbols, interval, num_iterations, start_date)
    if cache_key not in _SIGNALS_CACHE:
        logging.info(f"Cache miss for {interval} - collecting signals...")
        signals = collect_signals_and_data(strategy, symbols, interval, num_iterations, start_date)
        _SIGNALS_CACHE[cache_key] = signals
    else:
        logging.info(
            f"Cache hit for {interval} - using pre-collected signals ({len(_SIGNALS_CACHE[cache_key])} signals)")
        signals = _SIGNALS_CACHE[cache_key]
    results = {
        'trades': [],
        'win_count': 0,
        'loss_count': 0,
        'error_count': 0,
        'total_return_pct': 0.0,
        'max_drawdown_pct': 0.0,
        'win_rate': 0.0,
        'avg_win_pct': 0.0,
        'avg_loss_pct': 0.0,
        'profit_factor': 0.0,
        'equity_curve': []
    }
    all_trades = []
    for signal_data in signals:
        outcome = simulate_trade_outcome_cached(
            signal_data, tp_ratio, sl_ratio, add_buy_pct, save_charts
        )
        if outcome['error']:
            logging.error(f"Error in cached trade simulation for {signal_data['symbol']}")
            continue
        for trade in outcome['trades']:
            trade_info = {
                'symbol': signal_data['symbol'],
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
            else:
                results['error_count'] += 1
        if save_charts and not outcome['error']:
            plot_and_save_chart(
                df_100=signal_data['main_df'],
                symbol=signal_data['symbol'],
                interval=interval,
                backtest_index=signal_data['backtest_index'],
                is_detail_tf=False
            )
    all_trades.sort(key=lambda x: x['exit_time'])
    equity = 100.0
    equity_curve = [equity]
    max_equity = equity
    current_trades = []
    current_time = None
    for trade in all_trades:
        if current_time != trade['exit_time']:
            if current_trades:
                avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
                equity *= (1 + avg_return / 100)
                equity_curve.append(equity)
                max_equity = max(max_equity, equity)
                current_drawdown = ((max_equity - equity) / max_equity) * 100
                results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
            current_trades = [trade]
            current_time = trade['exit_time']
        else:
            current_trades.append(trade)
    if current_trades:
        avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
        equity *= (1 + avg_return / 100)
        equity_curve.append(equity)
        max_equity = max(max_equity, equity)
        current_drawdown = ((max_equity - equity) / max_equity) * 100
        results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
    total_trades = results['win_count'] + results['loss_count']
    if total_trades > 0:
        results['win_rate'] = (results['win_count'] / total_trades) * 100
        results['total_return_pct'] = ((equity_curve[-1] / equity_curve[0]) - 1) * 100
        win_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'WIN']
        loss_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'LOSS']
        if win_returns:
            results['avg_win_pct'] = sum(win_returns) / len(win_returns)
        if loss_returns:
            results['avg_loss_pct'] = sum(loss_returns) / len(loss_returns)
        total_wins = sum(win_returns) if win_returns else 0
        total_losses = abs(sum(loss_returns)) if loss_returns else 0
        results['profit_factor'] = total_wins / total_losses if total_losses != 0 else float('inf')
    results['equity_curve'] = equity_curve
    return results
