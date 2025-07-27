# app/indicators/fibonacci.py
def fibonacci_retracement(high_price: float, low_price: float, levels: list = None):
    """
    Given a high and low price, compute Fibonacci retracement levels between them.
    `levels` is a list of retracement percentages (0-1 range). Defaults to [0.236, 0.382, 0.5, 0.618, 0.786].
    Returns dict of level -> price.
    """
    if levels is None:
        levels = [0.236, 0.382, 0.5, 0.618, 0.786]
    if high_price < low_price:
        high_price, low_price = low_price, high_price  # swap to ensure high > low
    diff = high_price - low_price
    retracements = {}
    for r in levels:
        price_level = high_price - r * diff
        retracements[f"{int(r * 100)}%"] = price_level
    retracements["0%"] = low_price
    retracements["100%"] = high_price
    return retracements
