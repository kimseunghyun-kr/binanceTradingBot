"""
strategy_orchestrator.py
──────────────────────────────────────────────────────────────────────────
• Parallel first-pass proposal generation (ThreadPool)
• Serial second-pass WAL execution
• Unified load_component() with Protocol enforcement
• Reads OHLCV directly from read-only MongoDB
"""

from __future__ import annotations

import concurrent.futures as fut
import hashlib
import json
import logging
import sys
import time
from functools import partial
from typing import Any, Sequence, cast

import pandas as pd

from app.core.pydanticConfig.settings import get_settings
# ────────── domain objects & helpers ────────────────────────────────────
from entities.perpetuals.portfolio.PerpPortfolioManager import (
    PerpPortfolioManager,
)
from entities.portfolio.BasePortfolioManager import BasePortfolioManager
from entities.portfolio.policies.capacity.CapacityPolicy import (
    LegCapacity,
    SymbolCapacity,
)
from entities.portfolio.policies.fees.fees import (
    FEE_STATIC,
    FEE_PER_SYMBOL,
    SLIP_RANDOM,
    SLIP_ZERO,
)
from entities.portfolio.policies.interfaces import (
    CapacityPolicy,
    EventCostModel,
    SizingModel,
)
from entities.portfolio.policies.sizingModel.SizingModel import fixed_fraction
from entities.strategies.BaseStrategy import BaseStrategy
from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import (
    PeakEMAReversalStrategy,
)
from entities.tradeManager.TradeProposalBuilder import TradeProposalBuilder
from entities.tradeManager.policies.FillPolicy import (
    AggressiveMarketPolicy,
    VWAPDepthPolicy,
)
from entities.tradeManager.policies.interfaces import FillPolicy
from strategyOrchestrator.LoadComponent import load_component
from strategyOrchestrator.repository.candleRepository import CandleRepository

# ────────── built-in maps (callables only) ──────────────────────────────
FEE_MAP: dict[str, EventCostModel] = {
    "static": FEE_STATIC,
    "per_symbol": FEE_PER_SYMBOL,
    "__default__": FEE_STATIC,
}
SLIP_MAP: dict[str, EventCostModel] = {
    "random": SLIP_RANDOM,
    "zero": SLIP_ZERO,
    "__default__": SLIP_ZERO,
}
FILL_MAP: dict[str, type[FillPolicy]] = {
    "AggressiveMarketPolicy": AggressiveMarketPolicy,
    "VWAPDepthPolicy": VWAPDepthPolicy,
    "__default__": AggressiveMarketPolicy,
}
CAP_MAP: dict[str, type[CapacityPolicy]] = {
    "LegCapacity": LegCapacity,
    "SymbolCapacity": SymbolCapacity,
    "__default__": LegCapacity,
}
SIZE_MAP: dict[str, SizingModel] = {
    "fixed_fraction": fixed_fraction,
    "__default__": partial(fixed_fraction, 1.0),
}
STRAT_MAP: dict[str, type[BaseStrategy]] = {
    "PeakEMAReversalStrategy": PeakEMAReversalStrategy,
    "__default__": PeakEMAReversalStrategy,
}

_NEED_COLS = {"open_time", "open", "high", "low", "close"}


# ────────── utilities ───────────────────────────────────────────────────
def _new_logger() -> logging.Logger:
    """Return a tagged, non-propagating logger for a single back-test run."""
    tag = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    logger = logging.getLogger(f"Backtest_{tag}")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [" + tag + "] %(levelname)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _merge_symbol_frames(
    repo: CandleRepository,
    symbols: Sequence[str],
    interval: str,
    n_rows: int,
    lookback: int,
) -> pd.DataFrame | None:
    """Fetch and horizontally merge OHLCV frames for the given basket."""
    frames: list[pd.DataFrame] = []
    for sym in symbols:
        df = repo.fetch_candles(sym, interval, n_rows, newest_first=True)
        if df.empty or len(df) < lookback or df[_NEED_COLS].isna().any().any():
            return None
        df = df.sort_values("open_time").reset_index(drop=True)
        df.columns = pd.MultiIndex.from_product([[sym], df.columns])
        frames.append(df)

    return pd.concat(frames, axis=1)


# ────────── worker: build proposals for ONE job ─────────────────────────
def _proposals_for_job(
    job: dict[str, Any],
    interval: str,
    repo: CandleRepository,
    strategy: BaseStrategy,
    lookback: int,
    num_iter: int,
    tp: float,
    sl: float,
) -> list:
    symbols = job["symbols"]
    merged = _merge_symbol_frames(repo, symbols, interval, num_iter + lookback + 20, lookback)
    if merged is None:
        return []

    detail_int = "1h" if interval in {"1d", "1w"} else "15m"
    proposals: list = []
    last_idx = len(merged) - 1
    first_idx = max(lookback, len(merged) - num_iter)

    for i in range(last_idx, first_idx - 1, -1):
        window = merged.iloc[max(0, i - lookback + 1): i + 1]

        try:
            decision = strategy.decide(window, interval, tp_ratio=tp, sl_ratio=sl)
        except Exception:
            continue

        if decision.get("signal") != "BUY":
            continue

        entry_ts = int(window.index[-1])
        det_df = repo.fetch_candles(symbols[0], detail_int, 2000, start_time=entry_ts)
        if det_df.empty:
            continue

        proposals.append(
            TradeProposalBuilder(symbols[0], size=1.0, direction="LONG")
            .scale_in(1, 0.0, 0.0, "open")
            .bracket_exit(tp=tp, sl=sl)
            .set_entry_params(
                entry_price=float(decision["entry_price"]),
                tp_price=float(decision["tp_price"]),
                sl_price=float(decision["sl_price"]),
                entry_ts=entry_ts,
            )
            .build(det_df)
        )

    return proposals


# ────────── orchestrator core ───────────────────────────────────────────
def run_backtest(cfg: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for a single back-test run."""
    log = _new_logger()

    # ─── basic params ───────────────────────────────────────────────────
    symbols: list[str] = cfg["symbols"]
    interval: str = cfg["interval"]
    iterations: int = cfg.get("num_iterations", 60)
    tp_ratio: float = cfg.get("tp_ratio", 2.0)
    sl_ratio: float = cfg.get("sl_ratio", 1.0)
    workers: int = cfg.get("parallel_symbols", 4)
    market: str = cfg.get("market", "SPOT")

    # ─── plug-in resolution  (load_component() returns instances) ───────
    fee_model: EventCostModel = load_component(
        cfg.get("fee_model"), FEE_MAP, EventCostModel, "fee_model"
    )
    slippage_model: EventCostModel = load_component(
        cfg.get("slippage_model"), SLIP_MAP, EventCostModel, "slippage_model"
    )
    fill_policy: FillPolicy = cast(
        FillPolicy,
        load_component(cfg.get("fill_policy"), FILL_MAP, None, "fill_policy")(
            fee_model, slippage_model
        ),
    )
    capacity_policy: CapacityPolicy = load_component(
        cfg.get("capacity_policy"), CAP_MAP, CapacityPolicy, "capacity_policy"
    )
    sizing_model: SizingModel = load_component(
        cfg.get("sizing_model"), SIZE_MAP, SizingModel, "sizing_model"
    )
    strategy: BaseStrategy = load_component(
        cfg.get("strategy"), STRAT_MAP, BaseStrategy, "strategy"
    )

    # ─── data bootstrap ────────────────────────────────────────────────
    lookback = strategy.get_required_lookback()
    settings = get_settings()
    repo = CandleRepository(settings.mongo_slave_uri, settings.MONGO_DB_OHLCV)  # always slave / read-only
    jobs = strategy.work_units(symbols)

    # ─── parallel proposal generation ───────────────────────────────────
    proposals: list = []
    with fut.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(
                _proposals_for_job,
                job,
                interval,
                repo,
                strategy,
                lookback,
                iterations,
                tp_ratio,
                sl_ratio,
            ): job
            for job in jobs
        }
        for completed in fut.as_completed(future_map):
            try:
                proposals.extend(completed.result())
            except Exception as exc:  # pragma: no cover
                log.error("worker error: %s", exc)

    proposals.sort(key=lambda p: p.meta.entry_time)
    log.info("Proposals built: %d", len(proposals))

    # ─── portfolio bootstrap ───────────────────────────────────────────
    PM: type[BasePortfolioManager] = (
        PerpPortfolioManager if market.upper() == "PERP" else BasePortfolioManager
    )
    pm = PM(
        initial_cash=100_000,
        fee_model=fee_model,
        slippage_model=slippage_model,
        fill_policy=fill_policy,
        capacity_policy=capacity_policy,
        sizing_model=sizing_model,
    )

    # ─── timeline construction (serial WAL execution) ──────────────────
    detail_int = "1h" if interval in {"1d", "1w"} else "15m"
    detailed_candles = {
        s: repo.fetch_candles(s, detail_int, 10_000) for s in symbols
    }
    timeline = sorted(
        {
            int(row.open_time)
            for df in detailed_candles.values()
            for row in df.itertuples()
        }
    )
    price_map = {
        (s, int(row.open_time)): float(row.close)
        for s, df in detailed_candles.items()
        for row in df.itertuples()
    }

    p_idx = 0
    for ts in timeline:
        while p_idx < len(proposals) and proposals[p_idx].meta.entry_time <= ts:
            pm.try_execute(proposals[p_idx], now_ts=ts)
            p_idx += 1

        prices = {
            s: price_map[(s, ts)]
            for s in symbols
            if (s, ts) in price_map
        }
        pm.on_bar(ts, prices)

    if timeline:
        pm.on_bar(timeline[-1] + 1, {})  # final flush

    # ─── results ────────────────────────────────────────────────────────
    res = pm.get_results()
    res.update(
        {
            "symbol_count": len(symbols),
            "interval": interval,
            "strategy": strategy.__class__.__name__,
            "parallel_symbols": workers,
        }
    )
    return res


# ────────── CLI: stdin JSON → stdout JSON ───────────────────────────────
if __name__ == "__main__":
    try:
        _cfg = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"status": "failed", "error": "invalid JSON"}))
        sys.exit(1)

    print(json.dumps(run_backtest(_cfg), default=str))
