from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Protocol

import pandas as pd
from dateutil.parser import isoparse


class IDataProvider(Protocol):
    name: str
    async def list_symbols(self) -> list[str]: ...
    async def fetch_ohlcv(self, symbol: str, interval: str, start: datetime | None = None, **kw) -> pd.DataFrame: ...

class DataService:
    def __init__(self, providers: Sequence[IDataProvider]):
        self.providers = {p.name: p for p in providers}

    @staticmethod
    def _to_utc_naive(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is not None:  # aware → strip tz after shifting to UTC
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    # Symbol filter --------------------------------------------------------------------
    async def filter_symbols(
        self,
        *,
        market_cap_min: float | None = None,
        market_cap_max: float | None = None,
        provider: str = "CMC",
    ) -> list[str]:
        symbols = await self.providers[provider].list_symbols()
        # (market_cap filters already applied by CMC helper ‑ no extra work here)
        return symbols

    # OHLCV -----------------------------------------------------------------------------
    async def get_ohlcv(self, symbol: str, interval: str,
                        start: datetime | None = None, provider: str = "Binance",  **kw) -> pd.DataFrame:
        try:
            p = self.providers[provider]  # validate & pick
        except KeyError:
            raise KeyError(f"Unknown provider '{provider}'. Known: {list(self.providers)}")

        if isinstance(start, str):  # auto-coerce one more time
            start = isoparse(start)

        return await p.fetch_ohlcv(symbol, interval, start=start, **kw)

    async def ensure_ohlcv(
        self,
        symbol: str,
        interval: str,
        *,
        start: datetime | None = None,
        end:   datetime | None = None,
        provider: str = "Binance",
    ) -> None:
        """
        Guarantee the candles for [`start`, `end`] exist in Mongo.
        Only the missing *gaps* are downloaded.
        """
        from app.core.init_services import master_db_ohlcv_async      # <-- async DB
        from pymongo import ASCENDING, DESCENDING

        db  = master_db_ohlcv_async()
        col = db[f"{provider.lower()}_{interval}"]

        # ---------------------------------------------------- find current coverage

        # ────────── normalise bounds ──────────
        if isinstance(start, str):
            start = isoparse(start)
        if isinstance(end, str):
            end = isoparse(end)

        start = self._to_utc_naive(start)
        end = self._to_utc_naive(end)

        earliest = await col.find_one({"symbol": symbol},
                                      sort=[("timestamp", ASCENDING)])
        latest   = await col.find_one({"symbol": symbol},
                                      sort=[("timestamp", DESCENDING)])

        _2dt = lambda x: isoparse(x) if isinstance(x, str) else x

        earliest_ts = _2dt(earliest["timestamp"]) if earliest else None
        latest_ts = _2dt(latest["timestamp"]) if latest else None

        want_start = start or earliest_ts if earliest else start
        want_end = end or latest_ts if latest else end

        gaps: list[tuple[datetime, datetime | None]] = []

        # left-hand gap
        if want_start and (earliest_ts is None or earliest_ts > want_start):
            gaps.append((want_start, earliest_ts or want_end))

        # right-hand gap
        if want_end and (latest_ts is None or latest_ts < want_end):
            gaps.append((latest_ts or want_start, want_end))

        # ---------------------------------------------------- fill gaps
        for g_start, g_end in gaps:
            if g_start is None or g_end is None:
                continue

            df = await self.get_ohlcv(
                symbol, interval,
                start=g_start, provider=provider
            )
            if df is None or df.empty:
                continue

            df["timestamp"] = (
                pd.to_datetime(df["open_time"], unit="ms")  # or whatever field is time
                .dt.tz_localize(None)  # naive UTC
                .dt.to_pydatetime()  # pure Python datetime
            )

            # prepare docs for bulk-insert
            docs = df.to_dict("records")
            for d in docs:
                d["symbol"] = symbol      # partition key
                d["interval"] = interval

            try:
                await col.insert_many(docs, ordered=False)
            except Exception:  # dupes are fine
                pass
