"""
strategyOrchestrator.py
──────────────────────────────────────────────────────────────────────────
Global-clock back-test driver with single-pass fee / slippage handling.

Key design points
─────────────────
1.  **Global clock**All 1 h / 15m (daily/weekly) candles for every
    symbol are visited.  `PortfolioManager.on_bar()` therefore evaluates unrealised
    PnL, funding and exit events at the correct timestamps.

2.  **Single-pass costs**`TradeProposal` emits *raw* prices.  Only the ledger
    applies `fee_model(event)` and `slippage_model(event)` exactly once.

3.  **Spot vs Perp** Driver picks `BasePortfolioManager` or `PerpPortfolioManager`
    at runtime;

"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
import traceback
from types import SimpleNamespace
from typing import Dict, List, Any, Callable

import pandas as pd

from entities.perpetuals.portfolio.PerpPortfolioManager import PerpPortfolioManager
# ──────────────────────────────────────────────
# Project-specific imports – EDIT IF PATHS DIFFER
# ──────────────────────────────────────────────
from entities.portfolio.BasePortfolioManager import BasePortfolioManager
# Fee / slippage helpers
from entities.portfolio.fees.fees import (
    static_fee_model,
    per_symbol_fee_model,
    random_slippage_model,
)
from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import (
    PeakEMAReversalStrategy,
)
from entities.tradeManager.TradeMeta import TradeMeta
from entities.tradeManager.TradeProposal import TradeProposal
from strategyOrchestrator.Pydantic_config import settings  # ← holds DB creds
from strategyOrchestrator.repository.candleRepository import CandleRepository


# ──────────────────────────────────────────────
# Logging helpers
# ──────────────────────────────────────────────
def _get_logger() -> logging.Logger:
    tag = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    logger = logging.getLogger(f"Backtest_{tag}")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(f"%(asctime)s [{tag}] %(levelname)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# ──────────────────────────────────────────────
# Fee / slippage model wrappers
# ──────────────────────────────────────────────
def _const_event_model(val: float) -> Callable:
    return lambda _ev: float(val)


def _wrap_meta(fn_meta: Callable[[Any, str], float]) -> Callable:
    """
    Adapt a legacy signature (meta, action) -> float
    into the ledger‐expected (event) -> float.
    """

    def _inner(ev):
        meta = SimpleNamespace(symbol=ev.meta["symbol"])
        return fn_meta(meta, "entry")

    return _inner


# ──────────────────────────────────────────────
# Trade-proposal generation
# ──────────────────────────────────────────────
def _precheck_df(
        df: pd.DataFrame, need_cols: set[str], lookback: int, sym: str, log: logging.Logger
) -> pd.DataFrame | None:
    if df.empty or len(df) < lookback:
        log.warning(f"{sym}: insufficient candles – {len(df)} rows")
        return None
    if not df["open_time"].is_monotonic_increasing:
        df = df.sort_values("open_time").reset_index(drop=True)
    if df[need_cols].isna().any().any():
        log.warning(f"{sym}: NaNs in OHLCV")
        return None
    return df


def build_proposals(
        symbols: List[str],
        interval: str,
        symbol_data: Dict[str, Any],
        repo: CandleRepository,
        strategy,
        lookback: int,
        num_iter: int,
        tp_ratio: float,
        sl_ratio: float,
        log: logging.Logger,
) -> List[TradeProposal]:
    """
    Runs strategy.decide() over each symbol/window and builds TradeProposal objects.
    """
    need = {"open_time", "open", "high", "low", "close"}
    proposals: list[TradeProposal] = []

    for sym in symbols:
        try:
            df = pd.read_json(symbol_data[sym], orient="split")
        except Exception as exc:
            log.error(f"{sym}: failed to load JSON – {exc}")
            continue

        df = _precheck_df(df, need, lookback, sym, log)
        if df is None:
            continue

        last_idx = len(df) - 1
        first_idx = max(lookback, len(df) - num_iter)

        for i in range(last_idx, first_idx - 1, -1):
            window = df.iloc[max(0, i - lookback + 1): i + 1].copy()

            try:
                dec = strategy.decide(
                    window, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio
                )
            except Exception:
                log.error(f"{sym}@{int(df['open_time'].iloc[i])}\n" + traceback.format_exc())
                continue

            if dec.get("signal") != "BUY":
                continue

            entry_ts = int(df["open_time"].iloc[i])

            # Detail candles for post-entry monitoring
            detail_int = "1h" if interval in {"1d", "1w"} else "15m"
            detail_df = repo.fetch_candles(sym, detail_int, 2000, start_time=entry_ts)
            if detail_df.empty:
                log.warning(f"{sym}@{entry_ts}: no detail candles → skipped")
                continue

            meta = TradeMeta(
                symbol=sym,
                entry_time=entry_ts,
                entry_price=float(dec["entry_price"]),
                tp_price=float(dec["tp_price"]),
                sl_price=float(dec["sl_price"]),
                size=1,
            )
            proposals.append(TradeProposal(meta, detail_df))

    proposals.sort(key=lambda p: p.meta.entry_time)
    log.info(f"Built {len(proposals)} proposals")
    return proposals


# ──────────────────────────────────────────────
# Global-clock back-test
# ──────────────────────────────────────────────
def run_backtest(cfg: Dict[str, Any], log: logging.Logger) -> Dict[str, Any]:
    # ╭─ Config extraction ───────────────────────────────────────────╮
    symbols: List[str] = cfg["symbols"]
    interval: str = cfg["interval"]
    num_iter: int = cfg.get("num_iterations", 60)
    symbol_json: Dict[str, Any] = cfg["symbol_data"]

    tp_ratio: float = cfg.get("tp_ratio", 2.0)
    sl_ratio: float = cfg.get("sl_ratio", 1.0)
    add_pct: float = cfg.get("add_buy_pct", 5.0)

    fee_cfg = cfg.get("fee", 0.001)  # float | "per_symbol" | "static"
    slip_cfg = cfg.get("slippage", 0.0)  # float | "random"
    market = cfg.get("market", "SPOT")  # "SPOT" | "PERP"
    # ╰───────────────────────────────────────────────────────────────╯

    # Candle repository – supply your own DB creds via settings
    repo = CandleRepository(settings.MONGO_URI, settings.MONGO_DB)  # ### EDIT ME

    strategy = PeakEMAReversalStrategy()
    lookback = strategy.get_required_lookback()

    # 1 Generate proposals (raw prices, no costs baked-in)
    proposals = build_proposals(
        symbols,
        interval,
        symbol_json,
        repo,
        strategy,
        lookback,
        num_iter,
        tp_ratio,
        sl_ratio,
        log,
    )

    # 2 Instantiate portfolio manager with ONE pass cost models
    if isinstance(fee_cfg, (float, int)):
        fee_model = _const_event_model(fee_cfg)
    elif fee_cfg == "per_symbol":
        fee_model = _wrap_meta(per_symbol_fee_model)
    else:
        fee_model = _wrap_meta(static_fee_model)

    if isinstance(slip_cfg, (float, int)):
        slip_model = _const_event_model(slip_cfg)
    elif slip_cfg == "random":
        slip_model = _wrap_meta(random_slippage_model)
    else:
        slip_model = _const_event_model(0.0)

    PMClass = PerpPortfolioManager if market == "PERP" else BasePortfolioManager
    pm = PMClass(
        initial_cash=100_000,
        max_positions=5,
        fee_model=fee_model,
        slippage_model=slip_model,
    )

    # 3 Build a global timeline of candle close timestamps
    detail_int = "1h" if interval in {"1d", "1w"} else "15m"
    detail_candles: dict[str, pd.DataFrame] = {
        sym: repo.fetch_candles(sym, detail_int, 10_000)
        for sym in symbols
    }

    # Flatten to timestamp set
    timeline: list[int] = sorted(
        {
            int(row.open_time)
            for df in detail_candles.values()
            for row in df.itertuples()
        }
    )

    # Fast lookup of close price at (symbol, ts)
    close_map: dict[tuple[str, int], float] = {
        (sym, int(row.open_time)): float(row.close)
        for sym, df in detail_candles.items()
        for row in df.itertuples()
    }

    # 4 Global clock loop
    prop_idx = 0
    for ts in timeline:
        # a) admit proposals whose entry_time ≤ ts
        while prop_idx < len(proposals) and proposals[prop_idx].meta.entry_time <= ts:
            pm.try_execute(
                proposals[prop_idx],
                add_pct=add_pct
            )
            prop_idx += 1

        # b) mark-to-market at this bar
        prices = {
            sym: close_map[(sym, ts)]
            for sym in symbols
            if (sym, ts) in close_map
        }
        pm.on_bar(ts, prices)

    # Flush one extra bar to trigger exits that fell *inside* last candle
    if timeline:
        pm.on_bar(timeline[-1] + 1, {})

    # 5 Collect results
    result = pm.get_results()
    result.update(
        {
            "symbol_count": len(symbols),
            "market": market,
            "interval": interval,
            "strategy": strategy.__class__.__name__,
        }
    )
    return result


# ──────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────
def main():
    logger = _get_logger()
    try:
        cfg = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        logger.error("Invalid JSON on stdin")
        sys.exit(1)

    output = run_backtest(cfg, logger)
    print(json.dumps(output, default=str))


if __name__ == "__main__":
    main()
