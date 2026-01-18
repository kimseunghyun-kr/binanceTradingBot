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
import heapq
import json
import logging
import sys
import time
from typing import Any, Sequence, cast, Dict, List, Optional

import pandas as pd

from app.core.pydanticConfig.settings import get_settings
# ────────── domain objects & helpers ────────────────────────────────────
from strategyOrchestrator.entities.perpetuals.portfolio import (
    PerpPortfolioManager,
)
from strategyOrchestrator.entities.portfolio.BasePortfolioManager import BasePortfolioManager
from strategyOrchestrator.entities.config.registry import (
    FEE_MAP, SLIP_MAP, FILL_MAP, CAP_MAP, SIZE_MAP, STRAT_MAP
)
from strategyOrchestrator.LoadComponent import load_component
from strategyOrchestrator.entities.portfolio.policies.interfaces import CapacityPolicy, SizingModel, EventCostModel
from strategyOrchestrator.entities.strategies.BaseStrategy import BaseStrategy
from strategyOrchestrator.entities.tradeManager.TradeProposalBuilder import TradeProposalBuilder
from strategyOrchestrator.entities.tradeManager.TradeEvent import TradeEvent
from strategyOrchestrator.entities.tradeManager.TradeEventType import TradeEventType
from strategyOrchestrator.repository.candleRepository import CandleRepository  # Only for fallback

# ────────── built-in maps (callables only) ──────────────────────────────
_NEED_COLS = {"open_time", "open", "high", "low", "close"}

# Make sure Python is unbuffered (can also be set via env at runtime)
# In case it isn't, force flush on each log record:
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


# ────────── utilities ───────────────────────────────────────────────────
def _new_logger() -> logging.Logger:
    """Return a tagged logger for a single back-test run."""
    tag = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
    logger = logging.getLogger(f"Backtest_{tag}")
    logger.setLevel(logging.INFO)

    # Only add handler if not already present (avoid duplicate handlers in tests)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [" + tag + "] %(levelname)s: %(message)s")
        )
        logger.addHandler(handler)

    # Allow propagation so pytest's caplog can capture logs
    logger.propagate = True
    return logger


class PrefetchedDataSource:
    """
    Data source that uses pre-fetched OHLCV data instead of database.
    This is the PURE FUNCTION approach - no I/O, no side effects.
    """

    def __init__(self, ohlcv_data: Dict[str, Dict[str, List[Dict]]]):
        """
        Initialize with pre-fetched OHLCV data.

        Args:
            ohlcv_data: Dictionary with structure:
                {
                    "main": {symbol: [candle_dicts]},
                    "detailed": {symbol: [candle_dicts]}
                }
        """
        self.main_data = ohlcv_data.get("main", {})
        self.detailed_data = ohlcv_data.get("detailed", {})
        self._cache = {}  # Cache converted DataFrames

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        *,
        start_time: Optional[int] = None,
        newest_first: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch candles from pre-fetched data.

        This mimics CandleRepository.fetch_candles() but uses in-memory data.
        """
        # Determine which data source to use
        # For now, we'll use main data for strategy intervals and detailed for timeline
        cache_key = f"{symbol}:{interval}:{limit}:{start_time}:{newest_first}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get the appropriate data source
        if interval in {"1h", "15m"}:
            data_dict = self.detailed_data.get(symbol, [])
        else:
            data_dict = self.main_data.get(symbol, [])

        if not data_dict:
            logging.getLogger().warning(f"No pre-fetched data for {symbol} at {interval}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(data_dict)

        if df.empty:
            return df

        # Apply filters
        if start_time and "open_time" in df.columns:
            df = df[df["open_time"] <= start_time]

        # Sort
        if "open_time" in df.columns:
            df = df.sort_values("open_time", ascending=not newest_first)

        # Limit
        if len(df) > limit:
            df = df.head(limit) if not newest_first else df.tail(limit)

        # When newest_first=True, reverse back to ascending order after limiting
        # This matches the behavior of CandleRepository which returns data in ascending order
        if newest_first and "open_time" in df.columns:
            df = df.sort_values("open_time", ascending=True)

        df = df.reset_index(drop=True)

        # Cache result
        self._cache[cache_key] = df
        return df


def _merge_symbol_frames(
    repo,  # Can be CandleRepository or PrefetchedDataSource
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
    repo,  # Can be CandleRepository or PrefetchedDataSource
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
        sig = decision.get("signal")
        if sig not in ("BUY", "SELL"):
            continue
        # use actual timestamp from data instead of index as entry time
        sym0 = symbols[0]
        try:
            entry_ts = int(window[(sym0, "open_time")].iloc[-1])
        except Exception:
            entry_ts = int(window["open_time"].iloc[-1]) if "open_time" in window.columns else int(window.index[-1])

        det_df = repo.fetch_candles(symbols[0], detail_int, 2000, start_time=entry_ts)
        if det_df.empty:
            continue

        proposals.append(
            TradeProposalBuilder(symbols[0], size=1.0, direction= "LONG" if sig == "BUY" else "SHORT")
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
    fee_model = load_component(cfg.get("fee_model"), FEE_MAP, EventCostModel, "fee_model")()
    slippage_model = load_component(cfg.get("slippage_model"), SLIP_MAP, EventCostModel, "slippage_model")()
    fill_cls = load_component(cfg.get("fill_policy"), FILL_MAP, None, "fill_policy")
    fill_policy = fill_cls(fee_model, slippage_model)
    capacity_policy = load_component(cfg.get("capacity_policy"), CAP_MAP, CapacityPolicy, "capacity_policy")()
    sizing_model = load_component(cfg.get("sizing_model"), SIZE_MAP, SizingModel, "sizing_model")()
    strategy = load_component(cfg.get("strategy"), STRAT_MAP, BaseStrategy, "strategy")()

    # ─── data bootstrap ────────────────────────────────────────────────
    lookback = strategy.get_required_lookback()

    # ═══ PURE FUNCTION APPROACH: Use pre-fetched data if available ═══
    ohlcv_data = cfg.get("ohlcv_data")
    if ohlcv_data:
        log.info("Using pre-fetched OHLCV data (pure function mode)")
        repo = PrefetchedDataSource(ohlcv_data)
    else:
        # Fallback to database (legacy mode)
        log.warning("No pre-fetched data found, falling back to database access")
        settings = get_settings()
        repo = CandleRepository(settings.mongo_slave_uri, settings.MONGO_DB_OHLCV)

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
        initial_cash=cfg.get("initial_cash", 100_000),
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

    # Ensure all open positions are closed at final time
    if timeline:
        final_ts = timeline[-1]
        final_prices = {s: price_map.get((s, final_ts), 0.0) for s in symbols}
        for sym, pos in pm.tm.positions.items():
            if pos.qty != 0:
                close_ts = final_ts + 1
                close_ev = TradeEvent(
                    ts=close_ts,
                    price=float(final_prices.get(sym, 0.0)),
                    qty=-pos.qty,
                    event=TradeEventType.CLOSE,
                    meta={
                        "symbol": sym,
                        "exit": "FINAL",
                        "direction": "LONG" if pos.qty > 0 else "SHORT",
                        "orig_entry_px": float(getattr(pos, "avg_px", 0.0)),
                        "orig_entry_ts": final_ts,
                    }
                )
                heapq.heappush(pm._event_q, close_ev)
        pm.on_bar(final_ts + 1, {}) # final flush

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
    def read_config_from_stdin(timeout: int = 20) -> str | None:
        import select

        logging.getLogger().info(f"Waiting up to {timeout}s for config on stdin...")
        # Wait until there's something to read (non-blocking until timeout)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if not rlist:
            logging.getLogger().error("Timeout waiting for stdin input.")
            return None

        # Prefer readline so we don't hang forever if EOF isn't sent.
        raw = sys.stdin.readline()
        if raw == "":
            # If readline returned empty (maybe EOF already), try a full read as fallback.
            raw = sys.stdin.read()
        return raw

    # Immediate startup heartbeat so we know entrypoint ran.
    print("ENTRYPOINT STARTED", flush=True)
    logging.getLogger().info("Entry point reached, attempting to read config.")

    raw = read_config_from_stdin(timeout=20)
    if raw is None:
        error = {"status": "failed", "error": "no input received (timeout)"}
        print(json.dumps(error), flush=True)
        logging.getLogger().error("Exiting due to no stdin payload.")
        sys.exit(1)

    print("=== RAW INPUT START ===", flush=True)
    print(raw, flush=True)
    print("=== RAW INPUT END ===", flush=True)
    logging.getLogger().info("Bytes read: %d", len(raw.encode("utf-8", "ignore")))

    try:
        _cfg = json.loads(raw)
    except Exception as e:
        logging.getLogger().exception("Failed to parse JSON from stdin.")
        err = {"status": "failed", "error": "invalid JSON", "detail": str(e)}
        print(json.dumps(err), flush=True)
        sys.exit(1)

    logging.getLogger().info("Parsed JSON OK. Keys: %s", list(_cfg)[:20])

    result = run_backtest(_cfg)
    # Final output (flush immediately)
    print(json.dumps(result, default=str), flush=True)
    logging.getLogger().info("Backtest finished, result printed.")

