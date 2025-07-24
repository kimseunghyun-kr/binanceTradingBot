"""
strategyOrchestrator.py
──────────────────────────────────────────────────────────────────────────
• Parallel first-pass proposal generation (ThreadPool)
• Serial second-pass WAL execution
• Unified load_component() with Protocol enforcement
• Reads OHLCV directly from read-only MongoDB
"""

from __future__ import annotations

import concurrent.futures as fut
import hashlib, json, logging, sys, time
from typing import Any, Dict, List, cast

import pandas as pd

from app.core.pydanticConfig import settings
# ─────────── domain objects & helpers ───────────────────────────────── #
from entities.perpetuals.portfolio.PerpPortfolioManager import PerpPortfolioManager
from entities.portfolio.BasePortfolioManager           import BasePortfolioManager
from entities.strategies.BaseStrategy import BaseStrategy
from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import (
    PeakEMAReversalStrategy,
)
from entities.tradeManager.TradeProposalBuilder import TradeProposalBuilder
from strategyOrchestrator.repository.candleRepository import CandleRepository

# unified interfaces
from entities.portfolio.policies.interfaces import (
    EventCostModel, SizingModel, CapacityPolicy,
)
from entities.tradeManager.policies.interfaces import FillPolicy

from entities.portfolio.policies.fees.fees import (
    FEE_STATIC, FEE_PER_SYMBOL, SLIP_RANDOM, SLIP_ZERO,
)
from entities.portfolio.policies.capacity.CapacityPolicy import (
    LegCapacity, SymbolCapacity,
)
from entities.tradeManager.policies.FillPolicy import (
    AggressiveMarketPolicy, VWAPDepthPolicy,
)
from entities.portfolio.policies.sizingModel.SizingModel import fixed_fraction

# loader
from strategyOrchestrator.LoadComponent import load_component



# ─────────── built-in maps (all objects are callables) ──────────────── #
FEE_MAP  = {"static": FEE_STATIC,
            "per_symbol": FEE_PER_SYMBOL,
            "__default__": FEE_STATIC}

SLIP_MAP = {"random": SLIP_RANDOM,
            "zero":   SLIP_ZERO,
            "__default__": SLIP_ZERO}

FILL_MAP = {"AggressiveMarketPolicy": AggressiveMarketPolicy,
            "VWAPDepthPolicy":        VWAPDepthPolicy,
            "__default__":            AggressiveMarketPolicy}

CAP_MAP  = {"LegCapacity":    LegCapacity,
            "SymbolCapacity": SymbolCapacity,
            "__default__":    LegCapacity}

SIZE_MAP = {"fixed_fraction": fixed_fraction,
            "__default__":    (lambda frac=1.0: fixed_fraction(frac))}

STRAT_MAP = {"PeakEMAReversalStrategy": PeakEMAReversalStrategy,
             "__default__": PeakEMAReversalStrategy}

# ─────────── logging helper ─────────────────────────────────────────── #
def _log() -> logging.Logger:
    tag = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    lg  = logging.getLogger(f"Backtest_{tag}")
    lg.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter(f"%(asctime)s [{tag}] %(levelname)s: %(message)s"))
    lg.addHandler(h); lg.propagate = False
    return lg


# ─────────── worker: build proposals for ONE job ─────────────────────── #
def _proposals_for_job(job: Dict[str, Any], interval: str, repo: CandleRepository,
                       strategy, lookback: int, num_iter: int,
                       tp: float, sl: float) -> List:
    syms = job["symbols"]
    need = {"open_time", "open", "high", "low", "close"}

    # merge symbols’ candles horizontally
    dfs = []
    for s in syms:
        df = repo.fetch_candles(s, interval, num_iter + lookback + 20, newest_first=True)
        if df.empty or len(df) < lookback or df[need].isna().any().any():
            return []
        df = df.sort_values("open_time", ascending=True).reset_index(drop=True)
        df.columns = pd.MultiIndex.from_product([[s], df.columns])
        dfs.append(df)

    merged = pd.concat(dfs, axis=1)
    last, first = len(merged) - 1, max(lookback, len(merged) - num_iter)
    detail_int  = "1h" if interval in {"1d", "1w"} else "15m"
    proposals: list = []

    for i in range(last, first - 1, -1):
        window = merged.iloc[max(0, i - lookback + 1): i + 1]
        try:
            dec = strategy.decide(window, interval, tp_ratio=tp, sl_ratio=sl)
        except Exception:
            continue
        if dec.get("signal") != "BUY":
            continue

        entry_ts = int(window.index[-1])
        det_df   = repo.fetch_candles(syms[0], detail_int, 2000, start_time=entry_ts)
        if det_df.empty: continue

        proposals.append(
            TradeProposalBuilder(syms[0], size=1.0, direction="LONG")
            .scale_in(1, 0.0, 0.0, "open")
            .bracket_exit(tp = tp, sl = sl)
            .set_entry_params(
                entry_price=float(dec["entry_price"]),
                tp_price=float(dec["tp_price"]),
                sl_price=float(dec["sl_price"]),
                entry_ts=entry_ts,
            )
            .build(det_df)
        )

    return proposals


# ─────────── orchestrator core ───────────────────────────────────────── #
def run_backtest(cfg: Dict[str, Any]) -> Dict[str, Any]:
    lg = _log()

    symbols   : list  = cfg["symbols"]
    interval  : str   = cfg["interval"]
    iters     : int   = cfg.get("num_iterations", 60)
    tp_ratio  : float = cfg.get("tp_ratio", 2.0)
    sl_ratio  : float = cfg.get("sl_ratio", 1.0)
    workers   : int   = cfg.get("parallel_symbols", 4)
    market    : str   = cfg.get("market", "SPOT")

    # class
    fill_pol_cls = load_component(  # ← return a *class*
        cfg.get("fill_policy"),
        FILL_MAP,
        None,  # ← NO instantiation here
        "fill_policy",
    )

    # cost models --------------------------------------------------------
    fee_model: EventCostModel = load_component(
        cfg.get("fee_model"), FEE_MAP, EventCostModel, "fee_model"
    )
    slip_model: EventCostModel = load_component(
        cfg.get("slippage_model"), SLIP_MAP, EventCostModel, "slippage"
    )

    # fill policy (class → instance) ------------------------------------
    fill_cls = load_component(cfg.get("fill_policy"), FILL_MAP, None, "fill_policy")
    fill_pol: FillPolicy = cast(FillPolicy, fill_cls(fee_model, slip_model))

    # other plug-ins (instances) ----------------------------------------
    cap_pol: CapacityPolicy = load_component(
        cfg.get("capacity_policy"), CAP_MAP, CapacityPolicy, "capacity_policy"
    )
    size_mod: SizingModel = load_component(
        cfg.get("sizing_model"), SIZE_MAP, SizingModel, "sizing_model"
    )
    strategy: BaseStrategy = load_component(
        cfg.get("strategy"), STRAT_MAP, BaseStrategy, "strategy"
    )

    lookback = strategy.get_required_lookback()
    repo = CandleRepository(settings.MONGO_URI, settings.MONGO_DB, read_only=True)

    # job list (pairs/baskets) ------------------------------------------
    jobs = strategy.work_units(symbols)

    # parallel proposal build
    proposals: list = []
    with fut.ThreadPoolExecutor(max_workers=workers) as pool:
        fut_to_job = {
            pool.submit(_proposals_for_job, j, interval, repo,
                        strategy, lookback, iters, tp_ratio, sl_ratio): j
            for j in jobs
        }
        for f in fut.as_completed(fut_to_job):
            try: proposals.extend(f.result())
            except Exception as e: lg.error(f"worker err: {e}")

    proposals.sort(key=lambda p: p.meta.entry_time)
    lg.info(f"Proposals built: {len(proposals)}")

    # portfolio
    PM = PerpPortfolioManager if market == "PERP" else BasePortfolioManager
    pm = PM(
        initial_cash    = 100_000,
        fee_model       = fee_model,
        slippage_model  = slip_model,
        fill_policy     = fill_pol,
        capacity_policy = cap_pol,
        sizing_model    = size_mod,
    )

    # timeline
    detail_int = "1h" if interval in {"1d","1w"} else "15m"
    d_candles  = {s: repo.fetch_candles(s, detail_int, 10_000) for s in symbols}
    timeline   = sorted({int(r.open_time)
                         for df in d_candles.values() for r in df.itertuples()})
    price_map  = {(s, int(r.open_time)): float(r.close)
                  for s, df in d_candles.items() for r in df.itertuples()}

    pidx = 0
    for ts in timeline:
        while pidx < len(proposals) and proposals[pidx].meta.entry_time <= ts:
            pm.try_execute(proposals[pidx], now_ts=ts)
            pidx += 1
        prices = {s: price_map[(s, ts)]
                  for s in symbols if (s, ts) in price_map}
        pm.on_bar(ts, prices)

    if timeline:
        pm.on_bar(timeline[-1] + 1, {})

    res = pm.get_results()
    res.update({
        "symbol_count": len(symbols),
        "interval": interval,
        "strategy": strategy.__class__.__name__,
        "parallel_symbols": workers,
    })
    return res


# ─────────── CLI: stdin JSON → stdout JSON ───────────────────────────── #
if __name__ == "__main__":
    try:
        cfg = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"status":"failed","error":"invalid JSON"})); sys.exit(1)

    print(json.dumps(run_backtest(cfg), default=str))
