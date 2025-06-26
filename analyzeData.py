import os
import time
import logging
import pandas as pd
import mplfinance as mpf
from typing import Tuple
from config import ANALYSIS_SYMBOLS
from decision import kwon_strategy_decision
from indicators import compute_ema_series
from symbols import fetch_candles

###############################################################################
# PLOTTING CHARTS
###############################################################################
def plot_and_save_chart(
    df_100: pd.DataFrame,
    symbol: str,
    interval: str,
    backtest_index: int = None,
    is_detail_tf: bool = False,
    entry_price: float = None,
    tp_price: float = None,
    sl_price: float = None
):
    """
    Plots and saves a chart. 
    - If is_detail_tf=False (main timeframe), we compute and draw EMA lines 
      and also check we have enough candles for them (≥15).
    - If is_detail_tf=True (smaller timeframe), we skip EMA lines 
      and do not apply the min candle threshold checks.
    - Optionally, we add entry, TP, and SL lines for smaller timeframe charts.
    
    Args:
        df_100: DataFrame containing the candle data
        symbol: Trading pair symbol
        interval: Time interval
        backtest_index: If provided, the index of the signal candle during backtesting
        is_detail_tf: Flag to differentiate main vs. smaller timeframe chart
        entry_price: Entry price line on detail chart
        tp_price: Take Profit price line on detail chart
        sl_price: Stop Loss price line on detail chart
    """

    # For main timeframe: ensure enough candles for EMA
    if not is_detail_tf:
        if df_100.empty or len(df_100) < 15:
            logging.info(f"{symbol}({interval}): not enough candles ({len(df_100)}) to plot, skipping, sir.")
            return

        # Compute EMAs
        df_100["EMA15"] = compute_ema_series(df_100["close"], 15)
        df_100["EMA33"] = compute_ema_series(df_100["close"], 33)

        # If entire EMA columns are NaN, skip
        if df_100["EMA15"].isnull().all() or df_100["EMA33"].isnull().all():
            logging.info(f"{symbol}({interval}): EMA columns all NaN, skipping chart, sir.")
            return

    # Slice out candles around backtest_index (only for main timeframe)
    if backtest_index is not None and not is_detail_tf:
        start_idx = max(0, backtest_index - 29)  # 30 candles before
        end_idx = min(len(df_100), backtest_index + 5)  # up to 5 candles after
        df_plot = df_100.iloc[start_idx:end_idx].copy()
        signal_idx = backtest_index
    else:
        # For other or smaller timeframe, just copy all
        df_plot = df_100.copy()
        signal_idx = len(df_100) - 1

    # Convert to datetime index
    df_plot["Date"] = pd.to_datetime(df_plot["open_time"], unit="ms")
    df_plot.set_index("Date", inplace=True)
    df_plot.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume"
    }, inplace=True)

    # Drop rows that have missing O/H/L/C
    df_plot.dropna(
        axis=0,
        subset=["Open", "High", "Low", "Close"],
        how="any",
        inplace=True
    )
    if df_plot.empty or len(df_plot) < 2:
        logging.info(f"{symbol}({interval}): after dropna, insufficient data to plot, skipping, sir.")
        return

    # Prepare addplots
    apds = []
    if not is_detail_tf:
        # main timeframe => plot EMAs
        apds.append(mpf.make_addplot(df_plot["EMA15"], color="blue", width=1))
        apds.append(mpf.make_addplot(df_plot["EMA33"], color="yellow", width=2))

    # If backtest main timeframe, add vertical line/marker
    if backtest_index is not None and not is_detail_tf:
        signal_loc = backtest_index - start_idx
        if 0 <= signal_loc < len(df_plot):
            y_min = df_plot['Low'].min()
            y_max = df_plot['High'].max()
            signal_line = pd.Series(float('nan'), index=df_plot.index)
            signal_line.iloc[signal_loc] = y_max
            apds.append(mpf.make_addplot(signal_line, color='red', linestyle='--', width=1))

            marker_y = pd.Series(float('nan'), index=df_plot.index)
            marker_y.iloc[signal_loc] = df_plot['Low'].iloc[signal_loc] * 0.995
            apds.append(mpf.make_addplot(marker_y, type='scatter', marker='^', markersize=100, color='red'))

    # If detail timeframe, optionally plot entry/tp/sl lines
    if is_detail_tf and entry_price and tp_price and sl_price:
        # Creates a series of the same entry_price value for each point in time
        entry_series = pd.Series([entry_price] * len(df_plot), index=df_plot.index)
        tp_series    = pd.Series([tp_price]    * len(df_plot), index=df_plot.index)
        sl_series    = pd.Series([sl_price]    * len(df_plot), index=df_plot.index)
        
        # These are used to draw horizontal lines on the chart
        apds.append(mpf.make_addplot(entry_series, color='green', linestyle='-', width=1))
        apds.append(mpf.make_addplot(tp_series,    color='blue',  linestyle='--', width=1))
        apds.append(mpf.make_addplot(sl_series,    color='red',   linestyle='--', width=1))

    # Build filename
    if signal_idx >= len(df_100):
        signal_idx = len(df_100) - 1
    signal_open_time = df_100.iloc[signal_idx]["open_time"]
    time_str = pd.to_datetime(signal_open_time, unit="ms").strftime("%Y%m%d-%H%M%S")
    date_str = pd.to_datetime(signal_open_time, unit="ms").strftime("%Y%m%d")

    if is_detail_tf:
        out_file = f"{symbol}_{interval}_{time_str}_detail.png"
    else:
        out_file = f"{symbol}_{interval}_{time_str}.png"

    # Subfolder path
    if backtest_index is not None and not is_detail_tf:
        out_dir = os.path.join("YES_charts", interval, date_str)
    else:
        out_dir = os.path.join("YES_charts", interval)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_file)

    # Plot title
    if is_detail_tf:
        title_str = f"{symbol} ({interval}) - Smaller TF (TWAP or detail) chart"
    else:
        title_str = f"{symbol} ({interval}) - Main TF with EMAs"

    try:
        mpf.plot(
            df_plot,
            type='candle',
            style='charles',
            title=title_str,
            addplot=apds,
            savefig=out_path,
            axtitle="B" if (backtest_index is not None and not is_detail_tf) else "",
        )
        logging.info(f"Chart saved: {out_path}")
    except Exception as e:
        logging.error(f"Error plotting chart for {symbol} {interval}: {e}")

###############################################################################
# CURRENT ANALYSIS
###############################################################################
def fetch_and_analyze(symbol: str, interval: str) -> Tuple[str, str]:
    df = fetch_candles(symbol, interval, limit=100)
    if df.empty:
        return symbol, "NO DATA"
    final_decision = kwon_strategy_decision(df, interval)
    decision_str = final_decision.get('decision', 'NO')
    if decision_str.startswith("YES"):
        plot_and_save_chart(df, symbol, interval)
    return symbol, decision_str

def run_analysis_for_interval(interval: str, label: str):
    logging.info(f"\n=== {label} Analysis Start (Filtered Symbols) ===")
    symbols = ANALYSIS_SYMBOLS
    if not symbols:
        logging.info(f"No symbols available for {label} analysis, sir.")
        return
    results = []
    for sym in symbols:
        s, d = fetch_and_analyze(sym, interval)
        results.append((s, d))
    yes_list = [f"{x}({y})" for x, y in results if y.startswith("YES")]
    no_count = sum(1 for _, dec in results if dec == "NO")
    logging.info(f"\n[{label} Results]")
    if yes_list:
        logging.info("🚨 Buy signal (YES):")
        for item in yes_list:
            logging.info(f"  • {item}")
    else:
        logging.info("✅ No buy signals")
    logging.info(f"Total symbols reviewed: {len(symbols)}, Buy signals: {len(yes_list)}, No signals: {no_count}")
    logging.info(f"=== {label} Analysis End ===\n")

def run_weekly_analysis():
    run_analysis_for_interval("1w", "Weekly")

def run_daily_analysis():
    run_analysis_for_interval("1d", "Daily")
