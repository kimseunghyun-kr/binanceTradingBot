
import logging
from typing import Tuple
from marketDataApi.apiconfig.config import ANALYSIS_SYMBOLS
from marketDataApi.binance import fetch_candles
from strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy

from utils.plot import plot_and_save_chart


###############################################################################
# CURRENT ANALYSIS
###############################################################################
def fetch_and_analyze(symbol: str, interval: str) -> Tuple[str, str]:
    df = fetch_candles(symbol, interval, limit=100)
    if df.empty:
        return symbol, "NO DATA"
    peakEMAReversalStrategy = PeakEMAReversalStrategy()
    final_decision = peakEMAReversalStrategy.decide(df, interval)
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
