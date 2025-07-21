"""
Generic margin calculation utilities for linear / inverse perpetuals.
All numbers are in quote-currency (e.g. USDT) unless noted.
"""
from entities.perpetuals.contracts.perp_specs import PERP_SPECS


def position_value_usd(symbol: str, qty: float, mark_price: float) -> float:
    spec = PERP_SPECS[symbol]
    if spec.type == "linear":               # USDT-margined
        return qty * mark_price * spec.multiplier
    else:                                   # inverse (e.g. coin-margin)
        return qty * spec.multiplier / mark_price


def maintenance_margin_usd(
    symbol: str,
    qty: float,
    mark_price: float,
    mmr: float = 0.005,         # 0.5 % maintenance margin rate
) -> float:
    """
    Return maintenance margin requirement in USD.
    """
    return abs(position_value_usd(symbol, qty, mark_price)) * mmr
