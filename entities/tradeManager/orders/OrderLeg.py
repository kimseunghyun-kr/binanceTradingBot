import datetime
from dataclasses import dataclass
from typing import Union, Callable, Literal

import pandas as pd


@dataclass(frozen=True)
class OrderLeg:
    when: Union[int, datetime, Callable[[pd.Series], bool]]
    side: Literal["BUY", "SELL"]
    qty: float  # absolute or pct of original size
    px: Union[float, Callable[[pd.Series], float]]  # limit or trigger
    tif: Literal["GTC", "IOC", "FOK"] = "GTC"
    comment: str = ""
