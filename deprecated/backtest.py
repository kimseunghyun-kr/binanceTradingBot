# import logging
# import statistics
# import os
# import time
# import matplotlib.pyplot as plt
# from typing import List, Dict
# from config import ANALYSIS_SYMBOLS
# from deprecated.decision import kwon_strategy_decision
# from symbols import fetch_candles
# from analysis.analyzeData import plot_and_save_chart
# import pandas as pd
# import hashlib
# import json
#
# ###############################################################################
# # CACHING SYSTEM FOR GRID SEARCH OPTIMIZATION
# ###############################################################################
#
# # Global cache for signals and marketDataApi
# _SIGNALS_CACHE = {}
#
# def generate_cache_key(symbols: List[str], interval: str, num_iterations: int, start_date: str = None) -> str:
#     """Generate a unique cache key for the given parameters"""
#     cache_data = {
#         'symbols': sorted(symbols),
#         'interval': interval,
#         'num_iterations': num_iterations,
#         'start_date': start_date
#     }
#     cache_str = json.dumps(cache_data, sort_keys=True)
#     return hashlib.md5(cache_str.encode()).hexdigest()
#
# def collect_signals_and_data(
#     symbols: List[str],
#     interval: str,
#     num_iterations: int,
#     start_date: str = None
# ) -> List[Dict]:
#     """
#     Collect all buy signals and pre-fetch detailed marketDataApi for simulation.
#     This runs only once per unique parameter set.
#     """
#     logging.info(f"Collecting signals and fetching marketDataApi for {interval} (cache miss)...")
#     signals = []
#
#     for sym in symbols:
#         if start_date:
#             desired_analysis_start_dt = pd.Timestamp(start_date)
#             offset_periods = 35
#
#             fetch_start_dt = desired_analysis_start_dt
#             if interval == "1w":
#                 fetch_start_dt -= pd.Timedelta(weeks=offset_periods)
#             elif interval == "1d":
#                 fetch_start_dt -= pd.Timedelta(days=offset_periods)
#             else:
#                 logging.warning(f"Unhandled interval '{interval}' for fetch start_date offset.")
#
#             api_start_ts = int(fetch_start_dt.timestamp() * 1000)
#             df = fetch_candles(sym, interval, limit=2000, start_time=api_start_ts)
#
#             if df.empty or len(df) <= offset_periods:
#                 continue
#
#             first_start = 35
#             last_start = min(len(df) - 3, first_start + num_iterations - 1)
#
#             for i in range(first_start, last_start + 1):
#                 # Use dummy TP/SL ratios for signal detection only
#                 trade = analyze_backtest_candle(df, i, interval, tp_ratio=0.1, sl_ratio=0.05)
#                 if trade['signal'] == 'BUY':
#                     entry_time = df['open_time'].iloc[i]
#
#                     # Pre-fetch detailed marketDataApi for this signal
#                     real_entry_time, detailed_df = find_real_entry_time(
#                         sym, entry_time, trade['entry_price'], interval
#                     )
#
#                     signal_data = {
#                         'symbol': sym,
#                         'backtest_index': i,
#                         'initial_entry_time': entry_time,
#                         'initial_entry_price': trade['entry_price'],
#                         'real_entry_time': real_entry_time,
#                         'detailed_df': detailed_df,
#                         'main_df': df  # Keep main timeframe marketDataApi for charts
#                     }
#                     signals.append(signal_data)
#
#         else:
#             # Original logic - backward from recent marketDataApi
#             df = fetch_candles(sym, interval, limit=num_iterations + 35)
#             if df.empty or len(df) < 35:
#                 continue
#
#             last_start = len(df) - 3
#             first_start = last_start - (num_iterations - 1)
#             if first_start < 35:
#                 first_start = 35
#
#             for i in range(last_start, first_start - 1, -1):
#                 trade = analyze_backtest_candle(df, i, interval, tp_ratio=0.1, sl_ratio=0.05)
#                 if trade['signal'] == 'BUY':
#                     entry_time = df['open_time'].iloc[i]
#
#                     # Pre-fetch detailed marketDataApi for this signal
#                     real_entry_time, detailed_df = find_real_entry_time(
#                         sym, entry_time, trade['entry_price'], interval
#                     )
#
#                     signal_data = {
#                         'symbol': sym,
#                         'backtest_index': i,
#                         'initial_entry_time': entry_time,
#                         'initial_entry_price': trade['entry_price'],
#                         'real_entry_time': real_entry_time,
#                         'detailed_df': detailed_df,
#                         'main_df': df
#                     }
#                     signals.append(signal_data)
#
#     logging.info(f"Collected {len(signals)} buy signals with pre-fetched marketDataApi")
#     return signals
#
# def clear_signals_cache():
#     """Clear the signals cache to free memory"""
#     global _SIGNALS_CACHE
#     _SIGNALS_CACHE.clear()
#     logging.info("Signals cache cleared")
#
# def get_cache_info():
#     """Get information about current cache state"""
#     global _SIGNALS_CACHE
#     if not _SIGNALS_CACHE:
#         return "Cache is empty"
#
#     info = []
#     for cache_key, signals in _SIGNALS_CACHE.items():
#         info.append(f"Cache key: {cache_key[:8]}... - {len(signals)} signals")
#
#     return "\n".join(info)
#
# ###############################################################################
# # BACKTESTING LOGIC
# ###############################################################################
# def analyze_backtest_candle(df: pd.DataFrame, i: int, interval: str,
#                             tp_ratio: float = 0.1, sl_ratio: float = 0.05) -> dict:
#     """
#     Analyze a single candle for backtesting
#     """
#     start_i = max(0, i - 34)
#     sub_df = df.iloc[start_i : i+1].copy()
#     if len(sub_df) < 35:
#         return {'signal': 'NO'}
#
#     return kwon_strategy_decision(sub_df, interval, tp_ratio, sl_ratio)
#
# def get_detail_timeframe_params(main_interval: str) -> tuple:
#     """
#     Returns (detail_interval, num_candles) based on main timeframe
#     Weekly -> (1h, 336)  # 14 days * 24 hours for analysis
#     Daily -> (1h, 48)    # 2 days * 24 hours
#     Always using hourly candles for detailed analysis
#     """
#     if main_interval == "1w":
#         return "1h", 336  # Two weeks of hourly candles
#     elif main_interval == "1d":
#         return "1h", 48   # Two days of hourly candles
#     return "1h", 48  # Default to 48 hourly candles
#
# def find_real_entry_time(
#     symbol: str,
#     initial_entry_time: int,
#     entry_price: float,
#     main_interval: str,
#     scan_limit: int = 300  # Large enough to find entry point
# ) -> tuple:
#     """
#     Common function to find the real entry time by checking detailed timeframe marketDataApi.
#     Returns (real_entry_time, detail_df) where detail_df contains the exact number
#     of candles needed for the timeframe.
#     """
#     detail_interval, num_candles = get_detail_timeframe_params(main_interval)
#
#     # First scan for entry point
#     scan_df = fetch_candles(
#         symbol,
#         detail_interval,
#         limit=scan_limit,
#         start_time=initial_entry_time
#     )
#
#     real_entry_time = initial_entry_time
#     for _, candle in scan_df.iterrows():
#         if candle['low'] <= entry_price:
#             real_entry_time = candle['open_time']
#             break
#
#     # Now fetch exact number of candles from real entry time
#     detail_df = fetch_candles(
#         symbol,
#         detail_interval,
#         limit=num_candles,
#         start_time=real_entry_time
#     )
#
#     return real_entry_time, detail_df
#
# def simulate_trade_outcome(
#     symbol: str,
#     entry_time: int,
#     entry_price: float,
#     tp_price: float,
#     sl_price: float,
#     main_interval: str,
#     save_charts: bool = False,
#     add_buy_pct: float = 5.0
# ) -> dict:
#     """
#     Trade simulation with additional buy logic
#     - Initial buy when signal occurs
#     - Additional buy when price reaches -n% of initial entry
#     - Returns list of trades (max 2 trades)
#     """
#     # Find real entry time and get appropriate number of candles
#     detail_interval, num_candles = get_detail_timeframe_params(main_interval)
#
#     # First scan for entry point
#     scan_df = fetch_candles(
#         symbol,
#         detail_interval,
#         limit=300,
#         start_time=entry_time
#     )
#
#     real_entry_time = entry_time
#     for _, candle in scan_df.iterrows():
#         if candle['low'] <= entry_price:
#             real_entry_time = candle['open_time']
#             break
#
#     # Now fetch exact number of candles from real entry time
#     detailed_df = fetch_candles(
#         symbol,
#         detail_interval,
#         limit=num_candles,
#         start_time=real_entry_time
#     )
#
#     if detailed_df.empty:
#         return {
#             'trades': [],
#             'error': True
#         }
#
#     # Get real entry price as min(first_hour_open, ema)
#     first_hour_open = detailed_df.iloc[0]["open"]
#     real_entry_price = min(first_hour_open, entry_price)
#
#     # Calculate additional buy price
#     add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
#
#     # Recalculate TP/SL based on real entry price
#     tp_price = real_entry_price * (1 + (tp_price - entry_price) / entry_price)
#     sl_price = real_entry_price * (1 - (entry_price - sl_price) / entry_price)
#
#     # Track trades
#     trades = []
#
#     # First trade
#     first_trade = {
#         'entry_time': int(detailed_df.iloc[0]['open_time']),
#         'entry_price': real_entry_price,
#         'trade_num': 1
#     }
#     trades.append(first_trade)
#
#     # Variables for tracking
#     additional_buy_done = False
#     total_position = 0.25
#     avg_entry_price = real_entry_price
#
#     # Check each candle
#     for idx, candle in detailed_df.iterrows():
#         # Check for additional buy opportunity
#         if not additional_buy_done and candle['low'] <= add_buy_price:
#             # Additional buy at add_buy_price
#             additional_trade = {
#                 'entry_time': int(candle['open_time']),
#                 'entry_price': add_buy_price,
#                 'trade_num': 2
#             }
#             trades.append(additional_trade)
#
#             # Update position tracking
#             additional_buy_done = True
#             total_position = 0.50
#             avg_entry_price = (real_entry_price * 0.25 + add_buy_price * 0.25) / 0.50
#
#         # Check for SL hit
#         if candle['low'] <= sl_price:
#             # All positions exit at SL
#             for trade in trades:
#                 trade['exit_time'] = int(candle['open_time'])
#                 trade['exit_price'] = sl_price
#                 trade['return_pct'] = ((sl_price - trade['entry_price']) / trade['entry_price']) * 100
#                 trade['result'] = 'LOSS'
#                 trade['exit_type'] = 'SL'
#
#             if save_charts:
#                 plot_and_save_chart(
#                     df_100=detailed_df,
#                     symbol=symbol,
#                     interval=detail_interval,
#                     backtest_index=None,
#                     is_detail_tf=True,
#                     entry_price=avg_entry_price,
#                     tp_price=tp_price,
#                     sl_price=sl_price
#                 )
#
#             return {'trades': trades, 'error': False}
#
#         # Check for TP hit
#         if candle['high'] >= tp_price:
#             # All positions exit at TP
#             for trade in trades:
#                 trade['exit_time'] = int(candle['open_time'])
#                 trade['exit_price'] = tp_price
#                 trade['return_pct'] = ((tp_price - trade['entry_price']) / trade['entry_price']) * 100
#                 trade['result'] = 'WIN'
#                 trade['exit_type'] = 'TP'
#
#             if save_charts:
#                 plot_and_save_chart(
#                     df_100=detailed_df,
#                     symbol=symbol,
#                     interval=detail_interval,
#                     backtest_index=None,
#                     is_detail_tf=True,
#                     entry_price=avg_entry_price,
#                     tp_price=tp_price,
#                     sl_price=sl_price
#                 )
#
#             return {'trades': trades, 'error': False}
#
#     # No TP/SL hit - exit at last candle close
#     last_candle = detailed_df.iloc[-1]
#     last_close = last_candle['close']
#
#     for trade in trades:
#         trade['exit_time'] = int(last_candle['open_time'])
#         trade['exit_price'] = last_close
#         trade['return_pct'] = ((last_close - trade['entry_price']) / trade['entry_price']) * 100
#         trade['result'] = 'WIN' if last_close > trade['entry_price'] else 'LOSS'
#         trade['exit_type'] = 'CLOSE'
#
#     if save_charts:
#         plot_and_save_chart(
#             df_100=detailed_df,
#             symbol=symbol,
#             interval=detail_interval,
#             backtest_index=None,
#             is_detail_tf=True,
#             entry_price=avg_entry_price,
#             tp_price=tp_price,
#             sl_price=sl_price
#         )
#
#     return {'trades': trades, 'error': False}
#
# def simulate_trade_outcome_cached(
#     signal_data: Dict,
#     tp_ratio: float,
#     sl_ratio: float,
#     add_buy_pct: float,
#     save_charts: bool = False
# ) -> dict:
#     """
#     Simulate trade outcome using pre-cached detailed marketDataApi.
#     Much faster than original since no API calls needed.
#     """
#     detailed_df = signal_data['detailed_df']
#     symbol = signal_data['symbol']
#     initial_entry_price = signal_data['initial_entry_price']
#
#     if detailed_df.empty:
#         return {'trades': [], 'error': True}
#
#     # Calculate entry price as min(first_hour_open, ema)
#     first_hour_open = detailed_df.iloc[0]["open"]
#     real_entry_price = min(first_hour_open, initial_entry_price)
#
#     # Calculate TP/SL based on real entry price
#     tp_price = real_entry_price * (1 + tp_ratio)
#     sl_price = real_entry_price * (1 - sl_ratio)
#
#     # Calculate additional buy price
#     add_buy_price = real_entry_price * (1 - add_buy_pct / 100)
#
#     # Track trades
#     trades = []
#
#     # First trade
#     first_trade = {
#         'entry_time': int(detailed_df.iloc[0]['open_time']),
#         'entry_price': real_entry_price,
#         'trade_num': 1
#     }
#     trades.append(first_trade)
#
#     additional_buy_done = False
#
#     # Check each candle
#     for idx, candle in detailed_df.iterrows():
#         # Check for additional buy opportunity
#         if not additional_buy_done and candle['low'] <= add_buy_price:
#             additional_trade = {
#                 'entry_time': int(candle['open_time']),
#                 'entry_price': add_buy_price,
#                 'trade_num': 2
#             }
#             trades.append(additional_trade)
#             additional_buy_done = True
#
#         # Check for SL hit
#         if candle['low'] <= sl_price:
#             for trade in trades:
#                 trade['exit_time'] = int(candle['open_time'])
#                 trade['exit_price'] = sl_price
#                 trade['return_pct'] = ((sl_price - trade['entry_price']) / trade['entry_price']) * 100
#                 trade['result'] = 'LOSS'
#                 trade['exit_type'] = 'SL'
#
#             return {'trades': trades, 'error': False}
#
#         # Check for TP hit
#         if candle['high'] >= tp_price:
#             for trade in trades:
#                 trade['exit_time'] = int(candle['open_time'])
#                 trade['exit_price'] = tp_price
#                 trade['return_pct'] = ((tp_price - trade['entry_price']) / trade['entry_price']) * 100
#                 trade['result'] = 'WIN'
#                 trade['exit_type'] = 'TP'
#
#             return {'trades': trades, 'error': False}
#
#     # No TP/SL hit - exit at last candle close
#     last_candle = detailed_df.iloc[-1]
#     last_close = last_candle['close']
#
#     for trade in trades:
#         trade['exit_time'] = int(last_candle['open_time'])
#         trade['exit_price'] = last_close
#         trade['return_pct'] = ((last_close - trade['entry_price']) / trade['entry_price']) * 100
#         trade['result'] = 'WIN' if last_close > trade['entry_price'] else 'LOSS'
#         trade['exit_type'] = 'CLOSE'
#
#     return {'trades': trades, 'error': False}
#
# def backtest_timeframe(
#     symbols: List[str],
#     interval: str,
#     num_iterations: int,
#     tp_ratio: float = 0.1,    # Default 10% take profit
#     sl_ratio: float = 0.05,   # Default 5% stop loss
#     save_charts: bool = False,
#     add_buy_pct: float = 5.0,
#     start_date: str = None  # Format: "2021-01-01"
# ) -> dict:
#     """
#     Handles backtesting logic with additional buy approach.
#     When price drops to -n% from initial entry, make additional buy.
#     """
#     logging.info(f"Starting backtest for {interval} ...")
#     results = {
#         'trades': [],
#         'win_count': 0,
#         'loss_count': 0,
#         'error_count': 0,
#         'total_return_pct': 0.0,
#         'max_drawdown_pct': 0.0,
#         'win_rate': 0.0,
#         'avg_win_pct': 0.0,
#         'avg_loss_pct': 0.0,
#         'profit_factor': 0.0,
#         'equity_curve': []
#     }
#
#     all_trades = []
#
#     for sym in symbols:
#         if start_date:
#             desired_analysis_start_dt = pd.Timestamp(start_date)
#             offset_periods = 35 # Number of candles for initial EMA calculation
#
#             # Calculate the fetch_start_dt (35 periods before desired_analysis_start_dt)
#             fetch_start_dt = desired_analysis_start_dt
#             if interval == "1w":
#                 fetch_start_dt -= pd.Timedelta(weeks=offset_periods)
#             elif interval == "1d":
#                 fetch_start_dt -= pd.Timedelta(days=offset_periods)
#             # Add other interval cases if necessary for offset_periods
#             # elif interval == "1h":
#             #     fetch_start_dt -= pd.Timedelta(hours=offset_periods)
#             else:
#                 logging.warning(f"Unhandled interval '{interval}' for fetch start_date offset. Using desired_analysis_start_dt as fetch start.")
#
#             api_start_ts = int(fetch_start_dt.timestamp() * 1000)
#             logging.info(f"Fetching marketDataApi for {sym} ({interval}) from {fetch_start_dt.strftime('%Y-%m-%d')} for desired analysis start {start_date}")
#             df = fetch_candles(sym, interval, limit=2000, start_time=api_start_ts)
#
#             if df.empty or len(df) <= offset_periods:
#                 logging.warning(f"Skipping {sym} ({interval}), insufficient marketDataApi from {fetch_start_dt.strftime('%Y-%m-%d')} (got {len(df) if not df.empty else 0} candles, need > {offset_periods}) for desired analysis start {start_date}.")
#                 continue
#
#             # Use marketDataApi from start to end (chronological order)
#             # first_start will be 35, so df.iloc[35] corresponds to desired_analysis_start_dt
#             first_start = 35
#             last_start = min(len(df) - 3, first_start + num_iterations - 1)
#
#             for i in range(first_start, last_start + 1):  # Forward iteration
#                 trade = analyze_backtest_candle(df, i, interval, tp_ratio, sl_ratio)
#                 if trade['signal'] == 'BUY':
#                     entry_price = trade['entry_price']
#                     tp_price = trade['tp_price']
#                     sl_price = trade['sl_price']
#                     entry_time = df['open_time'].iloc[i]
#
#                     outcome = simulate_trade_outcome(
#                         sym,
#                         entry_time,
#                         entry_price,
#                         tp_price,
#                         sl_price,
#                         interval,
#                         save_charts,
#                         add_buy_pct
#                     )
#
#                     if outcome['error']:
#                         logging.error(f"Error in trade simulation for {sym} at {interval} at index {i}")
#                         continue
#
#                     for trade in outcome['trades']:
#                         trade_info = {
#                             'symbol': sym,
#                             'entry_time': trade['entry_time'],
#                             'entry_price': trade['entry_price'],
#                             'exit_time': trade['exit_time'],
#                             'exit_price': trade['exit_price'],
#                             'return_pct': trade['return_pct'],
#                             'outcome': trade['result'],
#                             'exit_type': trade['exit_type']
#                         }
#                         all_trades.append(trade_info)
#                         results['trades'].append(trade_info)
#
#                         if trade['result'] == 'WIN':
#                             results['win_count'] += 1
#                         elif trade['result'] == 'LOSS':
#                             results['loss_count'] += 1
#                         else:
#                             results['error_count'] += 1
#
#                     # Save main chart for the candle that triggered the buy
#                     if save_charts:
#                         plot_and_save_chart(
#                             df_100=df,
#                             symbol=sym,
#                             interval=interval,
#                             backtest_index=i,
#                             is_detail_tf=False
#                         )
#         else:
#             # Original logic - backward from recent marketDataApi
#             df = fetch_candles(sym, interval, limit=num_iterations + 35)
#             if df.empty or len(df) < 35:
#                 logging.info(f"Skipping {sym} at {interval}, insufficient marketDataApi.")
#                 continue
#
#             last_start = len(df) - 3
#             first_start = last_start - (num_iterations - 1)
#             if first_start < 35:
#                 first_start = 35
#
#             for i in range(last_start, first_start - 1, -1):
#                 trade = analyze_backtest_candle(df, i, interval, tp_ratio, sl_ratio)
#                 if trade['signal'] == 'BUY':
#                     entry_price = trade['entry_price']
#                     tp_price = trade['tp_price']
#                     sl_price = trade['sl_price']
#                     entry_time = df['open_time'].iloc[i]
#
#                     outcome = simulate_trade_outcome(
#                         sym,
#                         entry_time,
#                         entry_price,
#                         tp_price,
#                         sl_price,
#                         interval,
#                         save_charts,
#                         add_buy_pct
#                     )
#
#                     if outcome['error']:
#                         logging.error(f"Error in trade simulation for {sym} at {interval} at index {i}")
#                         continue
#
#                     for trade in outcome['trades']:
#                         trade_info = {
#                             'symbol': sym,
#                             'entry_time': trade['entry_time'],
#                             'entry_price': trade['entry_price'],
#                             'exit_time': trade['exit_time'],
#                             'exit_price': trade['exit_price'],
#                             'return_pct': trade['return_pct'],
#                             'outcome': trade['result'],
#                             'exit_type': trade['exit_type']
#                         }
#                         all_trades.append(trade_info)
#                         results['trades'].append(trade_info)
#
#                         if trade['result'] == 'WIN':
#                             results['win_count'] += 1
#                         elif trade['result'] == 'LOSS':
#                             results['loss_count'] += 1
#                         else:
#                             results['error_count'] += 1
#
#                     # Save main chart for the candle that triggered the buy
#                     if save_charts:
#                         plot_and_save_chart(
#                             df_100=df,
#                             symbol=sym,
#                             interval=interval,
#                             backtest_index=i,
#                             is_detail_tf=False
#                         )
#
#     # Process trades chronologically for equity curve
#     all_trades.sort(key=lambda x: x['exit_time'])
#     equity = 100.0
#     equity_curve = [equity]
#     max_equity = equity
#
#     current_trades = []
#     current_time = None
#
#     for trade in all_trades:
#         if current_time != trade['exit_time']:
#             if current_trades:
#                 avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
#                 equity *= (1 + avg_return/100)
#                 equity_curve.append(equity)
#                 max_equity = max(max_equity, equity)
#                 current_drawdown = ((max_equity - equity) / max_equity) * 100
#                 results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
#
#             current_trades = [trade]
#             current_time = trade['exit_time']
#         else:
#             current_trades.append(trade)
#
#     if current_trades:
#         avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
#         equity *= (1 + avg_return/100)
#         equity_curve.append(equity)
#         max_equity = max(max_equity, equity)
#         current_drawdown = ((max_equity - equity) / max_equity) * 100
#         results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
#
#     # Final stats
#     total_trades = results['win_count'] + results['loss_count']
#     if total_trades > 0:
#         results['win_rate'] = (results['win_count'] / total_trades) * 100
#         results['total_return_pct'] = ((equity_curve[-1] / equity_curve[0]) - 1) * 100
#
#         win_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'WIN']
#         loss_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'LOSS']
#
#         if win_returns:
#             results['avg_win_pct'] = sum(win_returns) / len(win_returns)
#         if loss_returns:
#             results['avg_loss_pct'] = sum(loss_returns) / len(loss_returns)
#
#         total_wins = sum(win_returns) if win_returns else 0
#         total_losses = abs(sum(loss_returns)) if loss_returns else 0
#         results['profit_factor'] = total_wins / total_losses if total_losses != 0 else float('inf')
#
#     results['equity_curve'] = equity_curve
#     return results
#
# def backtest_timeframe_cached(
#     symbols: List[str],
#     interval: str,
#     num_iterations: int,
#     tp_ratio: float = 0.1,
#     sl_ratio: float = 0.05,
#     save_charts: bool = False,
#     add_buy_pct: float = 5.0,
#     start_date: str = None
# ) -> dict:
#     """
#     Cached version of backtest_timeframe. Uses pre-collected signals and marketDataApi.
#     Much faster for grid search since API calls are minimized.
#     """
#     # Generate cache key
#     cache_key = generate_cache_key(symbols, interval, num_iterations, start_date)
#
#     # Check if signals are cached
#     if cache_key not in _SIGNALS_CACHE:
#         logging.info(f"Cache miss for {interval} - collecting signals...")
#         signals = collect_signals_and_data(symbols, interval, num_iterations, start_date)
#         _SIGNALS_CACHE[cache_key] = signals
#     else:
#         logging.info(f"Cache hit for {interval} - using pre-collected signals ({len(_SIGNALS_CACHE[cache_key])} signals)")
#         signals = _SIGNALS_CACHE[cache_key]
#
#     # Initialize results
#     results = {
#         'trades': [],
#         'win_count': 0,
#         'loss_count': 0,
#         'error_count': 0,
#         'total_return_pct': 0.0,
#         'max_drawdown_pct': 0.0,
#         'win_rate': 0.0,
#         'avg_win_pct': 0.0,
#         'avg_loss_pct': 0.0,
#         'profit_factor': 0.0,
#         'equity_curve': []
#     }
#
#     all_trades = []
#
#     # Process each cached signal
#     for signal_data in signals:
#         outcome = simulate_trade_outcome_cached(
#             signal_data, tp_ratio, sl_ratio, add_buy_pct, save_charts
#         )
#
#         if outcome['error']:
#             logging.error(f"Error in cached trade simulation for {signal_data['symbol']}")
#             continue
#
#         for trade in outcome['trades']:
#             trade_info = {
#                 'symbol': signal_data['symbol'],
#                 'entry_time': trade['entry_time'],
#                 'entry_price': trade['entry_price'],
#                 'exit_time': trade['exit_time'],
#                 'exit_price': trade['exit_price'],
#                 'return_pct': trade['return_pct'],
#                 'outcome': trade['result'],
#                 'exit_type': trade['exit_type']
#             }
#             all_trades.append(trade_info)
#             results['trades'].append(trade_info)
#
#             if trade['result'] == 'WIN':
#                 results['win_count'] += 1
#             elif trade['result'] == 'LOSS':
#                 results['loss_count'] += 1
#             else:
#                 results['error_count'] += 1
#
#         # Save main chart for the signal if needed
#         if save_charts and not outcome['error']:
#             plot_and_save_chart(
#                 df_100=signal_data['main_df'],
#                 symbol=signal_data['symbol'],
#                 interval=interval,
#                 backtest_index=signal_data['backtest_index'],
#                 is_detail_tf=False
#             )
#
#     # Process trades chronologically for equity curve (same as original)
#     all_trades.sort(key=lambda x: x['exit_time'])
#     equity = 100.0
#     equity_curve = [equity]
#     max_equity = equity
#
#     current_trades = []
#     current_time = None
#
#     for trade in all_trades:
#         if current_time != trade['exit_time']:
#             if current_trades:
#                 avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
#                 equity *= (1 + avg_return/100)
#                 equity_curve.append(equity)
#                 max_equity = max(max_equity, equity)
#                 current_drawdown = ((max_equity - equity) / max_equity) * 100
#                 results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
#
#             current_trades = [trade]
#             current_time = trade['exit_time']
#         else:
#             current_trades.append(trade)
#
#     if current_trades:
#         avg_return = sum(t['return_pct'] for t in current_trades) / len(current_trades)
#         equity *= (1 + avg_return/100)
#         equity_curve.append(equity)
#         max_equity = max(max_equity, equity)
#         current_drawdown = ((max_equity - equity) / max_equity) * 100
#         results['max_drawdown_pct'] = max(results['max_drawdown_pct'], current_drawdown)
#
#     # Final stats (same as original)
#     total_trades = results['win_count'] + results['loss_count']
#     if total_trades > 0:
#         results['win_rate'] = (results['win_count'] / total_trades) * 100
#         results['total_return_pct'] = ((equity_curve[-1] / equity_curve[0]) - 1) * 100
#
#         win_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'WIN']
#         loss_returns = [t['return_pct'] for t in all_trades if t['outcome'] == 'LOSS']
#
#         if win_returns:
#             results['avg_win_pct'] = sum(win_returns) / len(win_returns)
#         if loss_returns:
#             results['avg_loss_pct'] = sum(loss_returns) / len(loss_returns)
#
#         total_wins = sum(win_returns) if win_returns else 0
#         total_losses = abs(sum(loss_returns)) if loss_returns else 0
#         results['profit_factor'] = total_wins / total_losses if total_losses != 0 else float('inf')
#
#     results['equity_curve'] = equity_curve
#     return results
#
# def compute_stats(values: List[float]) -> dict:
#     """
#     Returns dict with mean, stdev, min, max for the given list of floats.
#     If the list is empty, returns placeholders.
#     """
#     if not values:
#         return {
#             "count": 0,
#             "mean": None,
#             "stdev": None,
#             "min": None,
#             "max": None
#         }
#     return {
#         "count": len(values),
#         "mean": statistics.mean(values),
#         "stdev": statistics.pstdev(values),
#         "min": min(values),
#         "max": max(values)
#     }
#
# def plot_backtest_histograms(results: dict, timeframe_label: str, out_dir: str, now_str: str):
#     """
#     Creates histograms for trade returns and outcomes
#     """
#     os.makedirs(out_dir, exist_ok=True)
#     win_returns = []
#     loss_returns = []
#
#     for trade in results['trades']:
#         if trade['outcome'] == 'WIN':
#             win_returns.append(trade['return_pct'])
#         elif trade['outcome'] == 'LOSS':
#             loss_returns.append(trade['return_pct'])
#
#     fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))
#     fig.suptitle(f"Trade Returns Distribution - {timeframe_label}", fontsize=16)
#
#     if win_returns:
#         ax1.hist(win_returns, bins=20, color='green', alpha=0.6, label='Winning Trades')
#         ax1.set_title("Winning Trades Distribution")
#         ax1.set_xlabel("Return %")
#         ax1.set_ylabel("Count")
#         ax1.legend()
#
#     if loss_returns:
#         ax2.hist(loss_returns, bins=20, color='red', alpha=0.6, label='Losing Trades')
#         ax2.set_title("Losing Trades Distribution")
#         ax2.set_xlabel("Return %")
#         ax2.set_ylabel("Count")
#         ax2.legend()
#
#     plt.tight_layout()
#     filename = f"returns_dist_{timeframe_label}_{now_str}.png"
#     out_path = os.path.join(out_dir, filename)
#     plt.savefig(out_path)
#     plt.close()
#     logging.info(f"Returns distribution chart saved for {timeframe_label}: {out_path}")
#
# def plot_equity_curve(equity_curve: List[float], timeframe_label: str,
#                       out_dir: str, now_str: str,
#                       tp_ratio: float = 0.1, sl_ratio: float = 0.05):
#     """
#     Plot equity curve
#     """
#     plt.figure(figsize=(10, 6))
#     plt.plot(equity_curve, label='Equity Curve')
#     plt.title(f'Equity Curve - {timeframe_label} with TP={round(tp_ratio * 100, 2)}% SL={round(sl_ratio * 100, 2)}%')
#     plt.xlabel('Trade Number')
#     plt.ylabel('Equity')
#     plt.grid(True)
#     plt.legend()
#
#     filename = f"equity_curve_{timeframe_label}_{now_str}.png"
#     out_path = os.path.join(out_dir, filename)
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     plt.savefig(out_path)
#     plt.close()
#     logging.info(f"Equity curve saved for {timeframe_label}: {out_path}")
#
# def run_backtesting(tf = "1w", tp_ratio: float = 0.1, sl_ratio: float = 0.05, save_charts: bool = False, add_buy_pct: float = 5.0, start_date: str = "2021-01-01", use_cache: bool = False):
#     """
#     Runs the backtest for a given timeframe
#     (1w or 1d) with the newly added additional buy approach
#
#     use_cache: If True, uses cached signals for faster grid search
#     """
#     symbols = ANALYSIS_SYMBOLS
#     if not symbols:
#         logging.info("No symbols available for backtesting, sir.")
#         return
#
#     if tf == "1w":
#         iterations = 200
#         label = "Weekly"
#     elif tf == "1d":
#         iterations = 900
#         label = "Daily"
#
#     logging.info("Starting the backtesting routine, sir...")
#     now_str = time.strftime("%Y%m%d-%H%M%S")
#
#     base_dir = "backtest_results"
#     tp_dir = f"{round(tp_ratio * 100, 1)}%"
#     sl_dir = f"{round(sl_ratio * 100, 1)}%"
#     # Add a subdirectory for the current add_buy_pct value
#     add_buy_dir_name = f"add_buy_{add_buy_pct:.1f}pct"
#     results_dir = os.path.join(base_dir, tf, tp_dir, sl_dir, add_buy_dir_name)
#     os.makedirs(results_dir, exist_ok=True)
#
#     lines = []
#     lines.append(f"Backtest Results at {now_str}\n")
#     lines.append("===================================\n")
#     if start_date:
#         lines.append(f"Backtest Period: From {start_date}\n")
#     if use_cache:
#         lines.append("Using cached signals for faster processing\n")
#
#     all_results = {}
#
#     # Choose backtest function based on cache setting
#     if use_cache:
#         results = backtest_timeframe_cached(symbols, tf, iterations, tp_ratio, sl_ratio, save_charts=save_charts, add_buy_pct=add_buy_pct, start_date=start_date)
#     else:
#         results = backtest_timeframe(symbols, tf, iterations, tp_ratio, sl_ratio, save_charts=save_charts, add_buy_pct=add_buy_pct, start_date=start_date)
#
#     all_results[tf] = results
#
#     lines.append(f"\nPerformance Metrics for {label} ({tf}) with TP={round(tp_ratio * 100, 2)}% SL={round(sl_ratio * 100, 2)}% Add.Buy={round(add_buy_pct, 2)}%:\n")
#     lines.append(f"Total Return: {results['total_return_pct']:.2f}%\n")
#     lines.append(f"Total Trades: {results['win_count'] + results['loss_count']}\n")
#     lines.append(f"Win Trades: {results['win_count']}\n")
#     lines.append(f"Loss Trades: {results['loss_count']}\n")
#     lines.append(f"Win Rate: {results['win_rate']:.2f}%\n")
#     lines.append(f"Average Win: {results['avg_win_pct']:.2f}%\n")
#     lines.append(f"Average Loss: {results['avg_loss_pct']:.2f}%\n")
#     lines.append(f"Profit Factor: {results['profit_factor']:.2f}\n")
#     lines.append(f"Maximum Drawdown: {results['max_drawdown_pct']:.2f}%\n")
#
#
#     lines_transactions = []
#     lines_transactions.append(f"=== BACKTEST PERIOD ===\n")
#     lines_transactions.append(f"Start Date: {start_date}\n")
#     lines_transactions.append(f"End Date: {time.strftime('%Y-%m-%d', time.localtime())}\n")
#     lines_transactions.append(f"Analysis Generated: {now_str}\n")
#     if use_cache:
#         lines_transactions.append(f"Processing: Cached signals used\n")
#     lines_transactions.append(f"========================\n\n")
#     lines_transactions.append(f"=== {label} ({tf}) with Add.Buy={round(add_buy_pct, 2)}% ===\n")
#     res = all_results[tf]
#     for trade in res['trades']:
#         lines_transactions.append(f"Symbol: {trade['symbol']}\n")
#         lines_transactions.append(f"Entry Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade['entry_time']/1000))}\n")
#         lines_transactions.append(f"Exit Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade['exit_time']/1000))}\n")
#         lines_transactions.append(f"Entry Price: {trade['entry_price']:.8f}\n")
#         lines_transactions.append(f"Exit Price: {trade['exit_price']:.8f}\n")
#         lines_transactions.append(f"Return: {trade['return_pct']:.2f}%\n")
#         lines_transactions.append(f"Outcome: {trade['outcome']}\n\n")
#
#     result_file = f"backtest_results_{now_str}.txt"
#     transactions_file = f"backtest_transactions_{now_str}.txt"
#     full_path = os.path.join(results_dir, result_file)
#     transactions_path = os.path.join(results_dir, transactions_file)
#     with open(full_path, "w") as f:
#         f.writelines(lines)
#     with open(transactions_path, "w") as f:
#         f.writelines(lines_transactions)
#
#     logging.info(f"Backtesting with TP={round(tp_ratio * 100, 2)}% SL={round(sl_ratio * 100, 2)}% complete, sir. Text results saved to: {full_path}")
#     logging.info(f"Transactions saved to: {transactions_path}")
#
#     plot_backtest_histograms(
#         results=all_results[tf],
#         timeframe_label=f"{label}({tf})",
#         out_dir=results_dir,
#         now_str=now_str
#     )
#
#     return all_results[tf]
#
# def plot_grid_search_results(grid_results, tf: str, save_path: str, add_buy_val_for_title: float = None):
#     """
#     Creates an interactive 3D plot of grid search results using plotly
#     """
#     try:
#         import plotly.graph_objects as go
#         import numpy as np
#     except ImportError:
#         logging.error("Plotly is required for 3D plotting. Please install plotly.")
#         return
#
#     tp_vals = [item[0] for item in grid_results]
#     sl_vals = [item[1] for item in grid_results]
#     returns = [item[2] for item in grid_results]
#
#     x = np.array(tp_vals)
#     y = np.array(sl_vals)
#     z = np.array(returns)
#
#     fig = go.Figure(data=[go.Scatter3d(
#         x=x * 100,
#         y=y * 100,
#         z=z,
#         mode='markers',
#         marker=dict(
#             size=6,
#             color=z,
#             colorscale='RdBu',
#             colorbar=dict(title='Return (%)'),
#             line_width=1
#         ),
#         text=[
#             f"TP={tp*100:.1f}%, SL={sl*100:.1f}%, Return={ret:.2f}%"
#             for tp, sl, ret in zip(x, y, z)
#         ],
#         hoverinfo='text'
#     )])
#
#     best_idx = np.argmax(z)
#     best_tp = x[best_idx]
#     best_sl = y[best_idx]
#     best_ret = z[best_idx]
#
#     fig.add_trace(go.Scatter3d(
#         x=[best_tp * 100],
#         y=[best_sl * 100],
#         z=[best_ret],
#         mode='markers+text',
#         marker=dict(
#             size=10,
#             color='gold',
#             symbol='diamond',
#             line=dict(color='black', width=2)
#         ),
#         text=[f"BEST: TP={best_tp*100:.1f}%, SL={best_sl*100:.1f}%, Return={best_ret:.2f}%"],
#         textposition="top center",
#         hoverinfo='text'
#     ))
#
#     fig_title = f'Grid Search Results ({tf.upper()})'
#     if add_buy_val_for_title is not None:
#         fig_title += f' - Add.Buy {add_buy_val_for_title:.1f}%'
#     fig_title += ' (Portfolio Analysis Based)'
#
#     fig.update_layout(
#         title=fig_title,
#         scene=dict(
#             xaxis_title='Take Profit (%)',
#             yaxis_title='Stop Loss (%)',
#             zaxis_title='Final Return (%)',
#             camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
#         ),
#         width=1000,
#         height=800
#     )
#
#     output_file_name = f'grid_search_results_{tf}'
#     if add_buy_val_for_title is not None:
#         output_file_name += f'_addbuy_{add_buy_val_for_title:.1f}'
#     output_file_name += f'_{int(time.time())}.html'
#
#     output_file = os.path.join(save_path, output_file_name)
#     fig.write_html(output_file)
#     logging.info(f"3D grid search plot saved to: {output_file}")
