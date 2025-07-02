import json
import os
import sys

import pandas as pd

# Import strategy dynamically; for demo, import a hardcoded one
from app.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy
from strategyOrchestrator.Pydantic_config import settings
from strategyOrchestrator.repository.candleRepository import CandleRepository


def simulate_trade(symbol, entry_time, entry_price, tp_price, sl_price, df, interval, add_buy_pct=5.0):
    # Your old _simulate_trade, except fetch_candles_func is replaced by already-passed df
    # For brevity, this version expects df is the detailed interval slice
    first_hour_open = df.iloc[0]["open"]
    real_entry_price = min(first_hour_open, entry_price)
    add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
    tp_price = real_entry_price * (1 + (tp_price - entry_price) / entry_price)
    sl_price = real_entry_price * (1 - (entry_price - sl_price) / entry_price)
    trades = [{
        'symbol': symbol,
        'entry_time': int(df.iloc[0]['open_time']),
        'entry_price': real_entry_price,
        'trade_num': 1
    }]
    additional_buy_done = False
    for idx, candle in df.iterrows():
        if not additional_buy_done and candle['low'] <= add_buy_price:
            trades.append({'symbol': symbol, 'entry_time': int(candle['open_time']), 'entry_price': add_buy_price,
                           'trade_num': 2})
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
    last_candle = df.iloc[-1]
    last_close = last_candle['close']
    for trade in trades:
        trade['exit_time'] = int(last_candle['open_time'])
        trade['exit_price'] = last_close
        trade['return_pct'] = ((last_close - trade['entry_price']) / trade['entry_price']) * 100
        trade['result'] = 'WIN' if last_close > trade['entry_price'] else 'LOSS'
        trade['exit_type'] = 'CLOSE'
    return {'trades': trades, 'error': False}


def aggregate_stats(all_trades):
    # Your old stats aggregation code—copy-paste as is
    results = {'trades': all_trades, 'win_count': 0, 'loss_count': 0, 'error_count': 0, 'total_return_pct': 0.0,
               'max_drawdown_pct': 0.0, 'win_rate': 0.0, 'avg_win_pct': 0.0, 'avg_loss_pct': 0.0, 'profit_factor': 0.0,
               'equity_curve': []}
    for trade in all_trades:
        if trade['result'] == 'WIN':
            results['win_count'] += 1
        elif trade['result'] == 'LOSS':
            results['loss_count'] += 1
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
        win_returns = [t['return_pct'] for t in all_trades if t['result'] == 'WIN']
        loss_returns = [t['return_pct'] for t in all_trades if t['result'] == 'LOSS']
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
    return results


def main():
    input_config = json.loads(sys.stdin.read())
    symbols = input_config["symbols"]
    interval = input_config["interval"]
    num_iterations = input_config["num_iterations"]
    symbol_data = input_config["symbol_data"]
    tp_ratio = input_config["tp_ratio"]
    sl_ratio = input_config["sl_ratio"]
    add_buy_pct = input_config["add_buy_pct"]

    # --- Initialize the repo ---
    repo = CandleRepository(settings.MONGO_URI, settings.MONGO_DB)

    strategy = PeakEMAReversalStrategy()
    lookback = strategy.get_required_lookback()
    all_trades = []

    for sym in symbols:
        df = pd.read_json(symbol_data[sym], orient="split")
        if df.empty or len(df) < lookback:
            continue
        last_index = len(df) - 1
        first_index = max(lookback, last_index - (num_iterations - 1))
        for i in range(last_index, first_index - 1, -1):
            window_df = df.iloc[max(0, i - lookback + 1): i + 1].copy()
            decision = strategy.decide(window_df, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio)
            if decision.get('signal') != 'BUY':
                continue
            entry_price = decision.get('entry_price')
            tp_price = decision.get('tp_price')
            sl_price = decision.get('sl_price')
            entry_time = int(df['open_time'].iloc[i])

            # --- Use repo to fetch the detailed simulation candles ---
            detail_interval = "1h"
            num_candles = 48 if interval == "1d" else 336 if interval == "1w" else 48
            detailed_df = repo.fetch_candles(sym, detail_interval, limit=num_candles, start_time=entry_time)
            if detailed_df.empty:
                continue

            outcome = simulate_trade(sym, entry_time, entry_price, tp_price, sl_price, detailed_df, interval,
                                     add_buy_pct)
            if outcome.get('error'):
                continue
            all_trades.extend(outcome['trades'])

    results = aggregate_stats(all_trades)
    print(json.dumps(results))


if __name__ == "__main__":
    main()
