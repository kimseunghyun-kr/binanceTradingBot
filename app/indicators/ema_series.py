from typing import Optional, Union

import pandas as pd


def compute_ema_series(
        df: pd.DataFrame,
        column: str = 'close',
        period: int = 33,
        start: Optional[Union[int, str, pd.Timestamp]] = None,
        end: Optional[Union[int, str, pd.Timestamp]] = None,
        adjust: bool = False,
        min_periods: Optional[int] = None,
        pad_invalid: bool = True,
        inplace: bool = False,
        out_col: Optional[str] = None
) -> pd.Series:
    data = df[column]
    if start is not None or end is not None:
        data = data.loc[start:end]
    ema = data.ewm(
        span=period,
        adjust=adjust,
        min_periods=min_periods if min_periods is not None else period
    ).mean()
    if pad_invalid:
        ema = ema.reindex(df.index)
    if inplace:
        col_name = out_col or f"{column}_ema{period}"
        df[col_name] = ema
    return ema
