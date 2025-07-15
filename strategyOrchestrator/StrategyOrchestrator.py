import json
import sys
import traceback
import pandas as pd
import logging
import hashlib
import time
from typing import List, Dict, Tuple, Any

from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy
from entities.portfolio.BasePortfolioManager import BasePortfolioManager
from entities.tradeProposal.TradeMeta import TradeMeta
from entities.tradeProposal.TradeProposal import TradeProposal
from strategyOrchestrator.Pydantic_config import settings
from strategyOrchestrator.repository.candleRepository import CandleRepository

NUM_DAY: int = 48
NUM_WEEK: int = 336
NUM_MONTH: int = 744

# --- Logging setup ---
def setup_logger(session_hash: str) -> logging.Logger:
    logger = logging.getLogger(f"Backtest_{session_hash}")
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(f'%(asctime)s [{session_hash[:8]}] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger

# --- Session hash for run identification ---
def get_session_hash(strategy: Any, interval: str, extra: str = "") -> str:
    hash_input = f"{time.time()}_{strategy.__class__.__name__}_{interval}_{extra}"
    return hashlib.sha256(hash_input.encode()).hexdigest()

def parse_input() -> Dict[str, Any]:
    try:
        return json.loads(sys.stdin.read())
    except Exception as e:
        logger.error(f"Error parsing input JSON: {e}")
        sys.exit(1)

def get_repo() -> CandleRepository:
    return CandleRepository(settings.MONGO_URI, settings.MONGO_DB)

# this will be replaced.
def get_strategy() -> PeakEMAReversalStrategy:
    return PeakEMAReversalStrategy()

def preprocess_dataframe(df: pd.DataFrame, lookback: int, sym: str, logger: logging.Logger) -> pd.DataFrame | None:
    if df.empty or len(df) < lookback:
        logger.warning(f"Skipping {sym}: empty DataFrame or insufficient data.")
        return None
    if not df['open_time'].is_monotonic_increasing:
        df = df.sort_values('open_time').reset_index(drop=True)
    # Optional: check for NAs, missing cols
    required_cols = {"open_time", "open", "high", "low", "close"}
    if not required_cols.issubset(df.columns):
        logger.warning(f"Skipping {sym}: DataFrame missing required columns.")
        return None
    if df.isna().any().any():
        logger.warning(f"Skipping {sym}: DataFrame has NaN values.")
        return None
    return df

def generate_trade_proposals(
    symbols: List[str],
    interval: str,
    num_iterations: int,
    symbol_data: Dict[str, Any],
    strategy: Any,
    lookback: int,
    repo: CandleRepository,
    tp_ratio: float,
    sl_ratio: float,
    add_buy_pct: float,
    logger: logging.Logger
) -> Tuple[List[TradeProposal], int]:
    """
    See previous docstring for full details.
    """
    proposals: List[TradeProposal] = []
    error_count: int = 0
    for sym in symbols:
        try:
            df = pd.read_json(symbol_data[sym], orient="split")
        except Exception as e:
            logger.error(f"Error loading DataFrame for {sym}: {e}")
            error_count += 1
            continue
        df = preprocess_dataframe(df, lookback, sym, logger)
        if df is None:
            error_count += 1
            continue
        last_index = len(df) - 1
        first_index = max(lookback, last_index - (num_iterations - 1))
        for i in range(last_index, first_index - 1, -1):
            window_df = df.iloc[max(0, i - lookback + 1): i + 1].copy()
            try:
                decision = strategy.decide(window_df, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio)
            except Exception as e:
                logger.error(f"Strategy error on {sym} @ {i}: {e}")
                logger.error(traceback.format_exc())
                error_count += 1
                continue
            if decision.get('signal') != 'BUY':
                continue
            entry_price = decision.get('entry_price')
            tp_price = decision.get('tp_price')
            sl_price = decision.get('sl_price')
            entry_time = int(df['open_time'].iloc[i])
            detail_interval = "1h"
            num_candles = NUM_DAY if interval == "1d" else NUM_WEEK if interval == "1w" else 48
            detailed_df = repo.fetch_candles(sym, detail_interval, limit=num_candles, start_time=entry_time)
            if detailed_df.empty:
                logger.warning(f"Empty detail candles for {sym} @ {entry_time}")
                error_count += 1
                continue
            meta = TradeMeta(
                symbol=sym,
                entry_time=entry_time,
                entry_price=entry_price,
                tp_price=tp_price,
                sl_price=sl_price,
                size=1
            )
            proposal = TradeProposal(meta, detailed_df)
            proposals.append(proposal)
    return proposals, error_count

def process_portfolio(
    proposals: List[TradeProposal],
    fee: float,
    slippage: float,
    add_buy_pct: float,
    logger: logging.Logger
) -> Tuple[BasePortfolioManager, int]:
    portfolio = BasePortfolioManager(
        initial_cash=100_000,
        max_positions=5,
        fee=fee,
        slippage=slippage
    )
    skipped_trades: int = 0
    proposals.sort(key=lambda p: p.meta.entry_time)
    for proposal in proposals:
        try:
            portfolio.try_execute(proposal, add_buy_pct=add_buy_pct)
        except Exception as e:
            logger.error(f"Error executing proposal {vars(proposal.meta)}: {e}")
            logger.error(traceback.format_exc())
            skipped_trades += 1
    return portfolio, skipped_trades

def run_backtest(input_config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
    symbols: List[str] = input_config.get("symbols", [])
    interval: str = input_config.get("interval")
    num_iterations: int = input_config.get("num_iterations", 50)
    symbol_data: Dict[str, Any] = input_config.get("symbol_data", {})
    tp_ratio: float = input_config.get("tp_ratio", 2.0)
    sl_ratio: float = input_config.get("sl_ratio", 1.0)
    add_buy_pct: float = input_config.get("add_buy_pct", 5.0)
    fee: float = input_config.get("fee", 0.001)
    slippage: float = input_config.get("slippage", 0.0005)

    repo: CandleRepository = get_repo()
    strategy: Any = get_strategy()
    lookback: int = strategy.get_required_lookback()
    session_hash: str = logger.name.split('_')[-1]

    logger.info(f"Backtest started with hash {session_hash}")
    proposals, error_count = generate_trade_proposals(
        symbols, interval, num_iterations, symbol_data, strategy, lookback,
        repo, tp_ratio, sl_ratio, add_buy_pct, logger
    )
    logger.info(f"Generated {len(proposals)} trade proposals with {error_count} errors.")
    portfolio, skipped_trades = process_portfolio(proposals, fee, slippage, add_buy_pct, logger)
    logger.info(f"Processed portfolio with {skipped_trades} skipped trades.")

    results = portfolio.get_results()
    results['symbol_count'] = len(symbols)
    results['error_count'] = error_count
    results['skipped_trades'] = skipped_trades
    results['session_hash'] = session_hash
    results['strategy'] = strategy.__class__.__name__
    results['interval'] = interval
    return results

def main():
    strategy = get_strategy()
    # For session hash, you can add more context fields if needed
    session_hash = get_session_hash(strategy, "interval_unknown")
    global logger
    logger = setup_logger(session_hash)

    input_config = parse_input()
    results = run_backtest(input_config, logger)
    print(json.dumps(results, default=str))

if __name__ == "__main__":
    main()
