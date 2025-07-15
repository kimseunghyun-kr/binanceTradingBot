def static_fee_model(meta, action="entry"):
    """Always returns the same fee percentage."""
    return 0.001  # 0.1%

def per_symbol_fee_model(meta, action="entry"):
    """Fee varies by symbol (could come from config/db)."""
    symbol_fees = {"BTCUSDT": 0.0005, "ETHUSDT": 0.001, "XRPUSDT": 0.0015}
    return symbol_fees.get(meta.symbol, 0.001)

import random
def random_slippage_model(meta, action="entry"):
    """Random slippage for realism."""
    return random.uniform(0, 0.001)  # 0–0.1% per trade