# defaults.py  (new small module)
DEFAULT_TOKEN = {
    "fee_model":       "static",
    "slippage_model":  "zero",
    "fill_policy":     "AggressiveMarketPolicy",
    "capacity_policy": "LegCapacity",
    "sizing_model":    "fixed_fraction",
    "strategy":        "PeakEMAReversalStrategy",
}
